require "sinatra/base"
require "sinatra/reloader"
require "time"
require "uri"

require_relative "session"
require_relative "eval_results"
require_relative "ansi"

module LogViz
  class App < Sinatra::Base
    # Auto-reloads changed .rb files on the next request — Ruby doesn't
    # hot-reload route/helper code by default, only the .erb views do, which
    # is exactly what kept producing "undefined method" errors after every
    # code change until the process was manually killed and restarted.
    # development? only true without RACK_ENV/APP_ENV set to something else,
    # so this never activates outside a normal local `bundle exec ruby
    # bin/log_viz` run.
    #
    # register alone only reliably tracks the main app file (this one) —
    # session.rb/eval_results.rb/ansi.rb are require_relative'd above,
    # *before* the reloader registers itself, so without also_reload it
    # never saw them being loaded and won't notice they've changed (caught
    # this the hard way: a heatmaps method added to eval_results.rb kept
    # 404/NoMethodError-ing until this glob was added). also_reload takes
    # any of these files changing as the signal to re-require all of them.
    configure(:development) do
      register Sinatra::Reloader
      also_reload File.join(__dir__, "*.rb")
    end

    set :root, File.expand_path("../..", __dir__)
    set :sessions_dir, ENV.fetch("LOG_VIZ_SESSIONS_DIR") {
      File.expand_path("../../../../.boukensha/sessions", __dir__)
    }
    set :eval_results_dir, ENV.fetch("LOG_VIZ_EVAL_RESULTS_DIR") {
      File.expand_path("../../../../../evals/results", __dir__)
    }
    # Matches the jaeger container's UI port from
    # week0_explore/infrastructure/observability (QUICKSTART.md's
    # "OpenTelemetry tracing" section) — just a link target, no API calls
    # made against it, so nothing breaks if Jaeger isn't actually running.
    set :jaeger_url, ENV.fetch("LOG_VIZ_JAEGER_URL", "http://localhost:16686")

    helpers do
      def session_paths
        Dir.glob(File.join(settings.sessions_dir, "*.jsonl")).sort.reverse
      end

      # Resolves a splat like "20260801T.../ollama_qwen3.6-35b-a3b/strict/0/session.jsonl"
      # to an absolute path, but only if it stays inside eval_results_dir —
      # eval log paths reach here via a URL, so a naive File.join would let
      # a "../../../../etc/passwd"-shaped splat read anything the process
      # can see. Returns nil (→ the route 404s) on either escape or a
      # missing file, rather than raising.
      def eval_run_log_path(splat_path)
        base = File.expand_path(settings.eval_results_dir)
        candidate = File.expand_path(File.join(base, splat_path.to_s))
        return nil unless candidate == base || candidate.start_with?(base + File::SEPARATOR)
        return nil unless File.file?(candidate)

        candidate
      end

      # The inverse: an eval run's absolute log_path (as evals/score.py
      # wrote it) back to the splat a /evals/runs/* URL needs. nil if the
      # log somehow isn't under eval_results_dir (e.g. results.jsonl was
      # copied in from elsewhere) — callers fall back to a plain path string.
      def eval_run_relative_log(run)
        raw = run.log_path.to_s
        return nil if raw.empty?

        # Current standard (evals/score.py's _relativize()): log_path is
        # already stored relative to eval_results_dir, specifically so a
        # local machine's absolute path never has to round-trip through
        # this file at all. The absolute-path branch below only exists for
        # rows written before that redaction existed.
        return raw unless raw.start_with?("/")

        base = File.expand_path(settings.eval_results_dir)
        abs = File.expand_path(raw)
        return nil unless abs.start_with?(base + File::SEPARATOR)

        abs.delete_prefix(base + File::SEPARATOR)
      end

      def eval_run_url(rel_path, suffix: "")
        encoded = rel_path.split("/").map { |seg| URI::DEFAULT_PARSER.escape(seg) }.join("/")
        "/evals/runs/#{encoded}#{suffix}"
      end

      def jaeger_trace_url(trace_id)
        return nil unless trace_id && !trace_id.empty?

        "#{settings.jaeger_url}/trace/#{trace_id}"
      end

      # "20260801T.../ollama_qwen3.6-35b-a3b/strict/0/session.jsonl" →
      # "Eval run — 20260801T.../ollama_qwen3.6-35b-a3b/strict/0" — generic
      # over the directory depth run_bakery.py happens to use today, rather
      # than assuming exactly batch/model/mode/rep (a future scenario runner
      # could nest differently).
      def eval_run_title(rel_path)
        parts = rel_path.split("/")
        parts.pop if parts.last == "session.jsonl"
        "Eval run &mdash; #{parts.join(' / ')}"
      end

      def format_time(iso)
        return "?" unless iso

        Time.parse(iso).strftime("%Y-%m-%d %H:%M:%S %z")
      rescue ArgumentError
        iso
      end

      def truncate(text, length = 100)
        flat = text.to_s.gsub(/\s+/, " ").strip
        flat.length > length ? "#{flat[0, length]}…" : flat
      end

      def format_args(args)
        return "" if args.nil? || args.empty?

        args.map { |k, v| "#{k}: #{v.inspect}" }.join(", ")
      end

      def ansi_html(text)
        Ansi.to_html(text)
      end

      def text_html(text)
        Ansi.escape_html(text)
      end

      # Plain (ANSI-stripped) first line — the room name, for a compact
      # <summary> label. The full text (still with its ANSI codes intact)
      # renders separately via ansi_html in the <details> body.
      def plain_first_line(text)
        text.to_s.gsub(Ansi::ESCAPE_RE, "").lines.first.to_s.strip
      end

      def fmt_tokens(n)
        n = n.to_i
        n >= 1000 ? format("%.1fk", n / 1000.0) : n.to_s
      end

      def pct(used, max)
        max.to_i.positive? ? [(used.to_f / max.to_i * 100).round, 100].min : 0
      end

      # Uncapped percentage for labels — shows >100% when a budget is exceeded
      # (bar widths still use the clamped `pct`).
      def pct_raw(used, max)
        max.to_i.positive? ? (used.to_f / max.to_i * 100).round : 0
      end

      # A small inline progress bar. `danger` paints it red (limit tripped).
      def progress_bar(used, max, label:, danger: false)
        width = pct(used, max)
        klass = danger ? "bar-fill danger" : "bar-fill"
        <<~HTML
          <div class="budget">
            <div class="budget-label">#{label}</div>
            <div class="bar"><div class="#{klass}" style="width: #{width}%"></div></div>
          </div>
        HTML
      end

      def fmt_cost(n)
        n.nil? ? "&mdash;" : format("$%.4f", n)
      end

      def fmt_cost_cell(cost, known: true)
        return "&mdash;" if cost.nil? || !known

        fmt_cost(cost)
      end

      # In-transcript chip (§2.3): live context size as a mini-bar scaled to the
      # context window, plus the turn spend accumulating toward its cap.
      def ctx_chip(usage, running, context_window:, max_turn_tokens:, model: nil, provider: nil, cost_usd: nil)
        return "" unless usage

        input = usage["input_tokens"].to_i
        out   = usage["output_tokens"].to_i
        cache = usage["cache_read_input_tokens"].to_i

        parts = []
        # Turn spend first and bar-backed — it's what trips max_tokens, so it's
        # the signal worth watching fill as you scroll.
        if max_turn_tokens.to_i.positive?
          danger = running.to_i > max_turn_tokens.to_i ? " danger" : ""
          parts << %(<span class="ctx-turn#{danger}">turn #{fmt_tokens(running)}/#{fmt_tokens(max_turn_tokens)}</span>)
          parts << %(<span class="ctx-bar"><span class="ctx-bar-fill#{danger}" style="width: #{pct(running, max_turn_tokens)}%"></span></span>)
        end
        # Live context size second, with a smaller mini-bar.
        parts << %(<span class="ctx-amt">ctx #{fmt_tokens(input)}</span>)
        if context_window.to_i.positive?
          parts << %(<span class="ctx-mini"><span class="ctx-mini-fill" style="width: #{pct(input, context_window)}%"></span></span>)
        end
        parts << %(<span class="ctx-out">+#{fmt_tokens(out)} out</span>)
        parts << %(<span class="ctx-cache">cached #{fmt_tokens(cache)}</span>) if cache.positive?
        parts << %(<span class="ctx-cost">#{fmt_cost(cost_usd)}</span>) unless cost_usd.nil?
        parts << %(<span class="ctx-model">#{[provider, model].compact.join(" / ")}</span>) if provider || model

        %(<span class="ctx-chip">#{parts.join("\n")}</span>)
      end

      # Inline SVG sparkline of per-iteration input_tokens across the session.
      # `points` is the Session#usage_series; faint vertical lines mark turn
      # boundaries, a notch marks compactions. No JS, no chart library.
      def sparkline(points, max:, width: 640, height: 48)
        return "" if points.length < 2

        max = 1 if max.to_i < 1
        step = width.to_f / (points.length - 1)

        coords = points.each_with_index.map do |p, i|
          x = (i * step).round(1)
          y = (height - (p.input.to_f / max * (height - 4)) - 2).round(1)
          "#{x},#{y}"
        end.join(" ")

        # Faint vertical rule at each turn's first iteration (after turn 1).
        boundaries = points.each_with_index.select { |p, i| i.positive? && p.iteration == 1 }
        rules = boundaries.map do |_p, i|
          x = (i * step).round(1)
          %(<line class="spark-turn" x1="#{x}" y1="0" x2="#{x}" y2="#{height}"/>)
        end.join

        <<~SVG
          <svg class="spark" viewBox="0 0 #{width} #{height}" preserveAspectRatio="none" role="img" aria-label="input tokens per iteration">
            #{rules}
            <polyline class="spark-line" points="#{coords}"/>
          </svg>
        SVG
      end

      # Status colors, not categorical — PASS/FAIL is a state, not an
      # identity, so color here is reserved and never doubles as a model/
      # series encoding. Values from the project's data-viz palette
      # (references/palette.md), both clear 3:1 contrast on a white surface.
      EVAL_STATUS_COLOR = { pass: "#0ca30c", fail: "#d03b3b" }.freeze

      # The project's data-viz palette's sequential blue ramp (step 100 →
      # step 700, light → dark), used unmodified for the heatmap's magnitude
      # encoding (success rate is a proportion, one hue, light→dark — never
      # a rainbow). Interpolated between these documented stops rather than
      # snapped to the nearest one, since a heatmap's fill is continuous
      # (0-100%), not the small number of discrete ordinal tiers the palette
      # doc's other sequential use cases (funnel stages, tiers) need.
      HEATMAP_BLUE_STEPS = %w[
        #cde2fb #b7d3f6 #9ec5f4 #86b6ef #6da7ec #5598e7
        #3987e5 #2a78d6 #256abf #1c5cab #184f95 #104281 #0d366b
      ].freeze

      def _hex_to_rgb(hex)
        hex.delete_prefix("#").scan(/../).map { |h| h.to_i(16) }
      end

      def _blend_hex(hex_a, hex_b, t)
        rgb = _hex_to_rgb(hex_a).zip(_hex_to_rgb(hex_b)).map { |a, b| (a + ((b - a) * t)).round }
        format("#%02x%02x%02x", *rgb)
      end

      # fraction: 0.0-1.0, or nil for "no data" (a neutral gray, not part of
      # the blue ramp at all — no data and "0% success" must not look alike).
      def heatmap_fill(fraction)
        return "#e1e0d9" if fraction.nil?

        steps = HEATMAP_BLUE_STEPS
        pos = fraction.clamp(0.0, 1.0) * (steps.length - 1)
        lo = pos.floor
        hi = [lo + 1, steps.length - 1].min
        _blend_hex(steps[lo], steps[hi], pos - lo)
      end

      # White or dark ink, picked from the actual interpolated fill's
      # luminance so text stays readable across the whole ramp — a single
      # fixed ink color would fail contrast at one end or the other. Text
      # itself still wears a fixed ink role (white/dark), never the series
      # hue, per the palette doc's "text wears text tokens" rule; this just
      # picks which of the two per cell.
      def heatmap_text_color(fraction)
        return "#0b0b0b" if fraction.nil?

        r, g, b = _hex_to_rgb(heatmap_fill(fraction))
        luminance = ((0.299 * r) + (0.587 * g) + (0.114 * b)) / 255.0
        luminance > 0.55 ? "#0b0b0b" : "#ffffff"
      end

      # Inline SVG scatter of one eval group's runs: iterations used (x) vs
      # wall-clock duration (y), colored by outcome. One axis, no dual-scale
      # (see the project's dataviz skill's non-negotiables) — model/mode
      # identity is handled by faceting (one chart per EvalGroup, which
      # already is one scenario+model+mode), not by adding a second color
      # channel here. No JS, no chart library — plain SVG with a native
      # <title> per point standing in for a hover tooltip.
      def scatter_plot(runs, width: 620, height: 260)
        points = runs.select { |r| r.iteration_count && r.duration_s&.positive? }
        return "" if points.length < 2

        pad = { left: 42, right: 12, top: 12, bottom: 30 }
        plot_w = width - pad[:left] - pad[:right]
        plot_h = height - pad[:top] - pad[:bottom]

        max_x = [points.map(&:iteration_count).max, 1].max
        max_y = [points.map(&:duration_s).max, 1.0].max

        x_of = ->(v) { (pad[:left] + (v.to_f / max_x) * plot_w).round(1) }
        y_of = ->(v) { (pad[:top] + plot_h - (v.to_f / max_y) * plot_h).round(1) }

        grid = (0..4).flat_map do |i|
          xt = (max_x * i / 4.0).round
          yt = max_y * i / 4.0
          x = x_of.call(xt)
          y = y_of.call(yt)
          [
            %(<line class="scatter-grid" x1="#{x}" y1="#{pad[:top]}" x2="#{x}" y2="#{pad[:top] + plot_h}"/>),
            %(<text class="scatter-tick" x="#{x}" y="#{pad[:top] + plot_h + 16}" text-anchor="middle">#{xt}</text>),
            %(<line class="scatter-grid" x1="#{pad[:left]}" y1="#{y}" x2="#{pad[:left] + plot_w}" y2="#{y}"/>),
            %(<text class="scatter-tick" x="#{pad[:left] - 6}" y="#{y + 3}" text-anchor="end">#{yt.round(yt < 10 ? 1 : 0)}</text>),
          ]
        end.join

        dots = points.map do |r|
          cx = x_of.call(r.iteration_count)
          cy = y_of.call(r.duration_s)
          color = r.success? ? EVAL_STATUS_COLOR[:pass] : EVAL_STATUS_COLOR[:fail]
          label = "#{r.success? ? 'PASS' : 'FAIL'} — batch #{r.batch_id} rep #{r.repetition} — " \
                  "#{r.iteration_count} iterations, #{r.duration_s.round(1)}s"
          %(<circle class="scatter-dot" cx="#{cx}" cy="#{cy}" r="5" fill="#{color}"><title>#{text_html(label)}</title></circle>)
        end.join

        <<~SVG
          <svg class="scatter" viewBox="0 0 #{width} #{height}" role="img" aria-label="iterations used vs duration, colored by pass or fail">
            #{grid}
            <line class="scatter-axis" x1="#{pad[:left]}" y1="#{pad[:top]}" x2="#{pad[:left]}" y2="#{pad[:top] + plot_h}"/>
            <line class="scatter-axis" x1="#{pad[:left]}" y1="#{pad[:top] + plot_h}" x2="#{pad[:left] + plot_w}" y2="#{pad[:top] + plot_h}"/>
            <text class="scatter-axis-label" x="#{pad[:left] + plot_w / 2}" y="#{height - 2}" text-anchor="middle">iterations used</text>
            <text class="scatter-axis-label" x="12" y="#{pad[:top] + plot_h / 2}" text-anchor="middle" transform="rotate(-90 12 #{pad[:top] + plot_h / 2})">duration (s)</text>
            #{dots}
          </svg>
        SVG
      end
    end

    get "/" do
      @sessions = session_paths.map { |path| Session.load(path) }
      # Lightweight on purpose: reads evals/results/*.jsonl's own summary
      # fields (already read for /evals), not a full Session.load per run —
      # with "a lot of tests" accumulating, parsing every eval trial's full
      # transcript just to render this index would get slow fast. Capped to
      # the most recent 20; /evals has the complete, groupable picture.
      all_eval_runs = EvalResults.load_all(settings.eval_results_dir)
      @eval_run_total = all_eval_runs.length
      @eval_runs = all_eval_runs.sort_by { |r| [r.batch_id.to_s, r.repetition.to_i] }.reverse.first(20)
      erb :index
    end

    get "/sessions/:id" do
      id   = File.basename(params[:id])
      path = File.join(settings.sessions_dir, "#{id}.jsonl")
      halt 404, "Session not found: #{id}" unless File.file?(path)

      @session = Session.load(path)
      @current_view = :transcript
      erb :session
    end

    # Prototype alternative to the transcript above: the same session data,
    # regrouped into one narrative "beat" per turn instead of a flat
    # chronological event log. See docs/plans/15_otel_tracing.md (§3/§4 of
    # the lesson this came out of) for what this is comparing against.
    get "/sessions/:id/story" do
      id   = File.basename(params[:id])
      path = File.join(settings.sessions_dir, "#{id}.jsonl")
      halt 404, "Session not found: #{id}" unless File.file?(path)

      @session = Session.load(path)
      @current_view = :story
      erb :story
    end

    get "/evals" do
      @groups = EvalResults.groups(EvalResults.load_all(settings.eval_results_dir))
      @heatmaps = EvalResults.heatmaps(@groups)
      erb :evals
    end

    # Eval trial logs are written by the same Logger as regular sessions
    # (evals/boukensha_agent.py's driver calls the same boukensha.run_reprompted(),
    # which shares boukensha/logger.py) — same phase-tagged JSONL, so the
    # existing Session/transcript/story views work unmodified. These just
    # resolve a path under eval_results_dir instead of an :id under
    # sessions_dir, and point _header.erb's back/toggle links at /evals
    # instead of the session index (see _header.erb's @back_path etc.).
    #
    # The /story variant is defined FIRST: Sinatra's plain "/evals/runs/*"
    # splat is greedy with nothing after it to constrain it, so it would
    # swallow a trailing "/story" into the splat itself and this route
    # would never be reached if it came second.
    get "/evals/runs/*/story" do
      path = eval_run_log_path(params[:splat][0])
      halt 404, "Eval session log not found" unless path

      rel = params[:splat][0]
      @session = Session.load(path)
      @current_view = :story
      @back_path = "/evals"
      @back_label = "Evals"
      @header_title = eval_run_title(rel)
      @transcript_path = eval_run_url(rel)
      @story_path = eval_run_url(rel, suffix: "/story")
      erb :story
    end

    get "/evals/runs/*" do
      path = eval_run_log_path(params[:splat][0])
      halt 404, "Eval session log not found" unless path

      rel = params[:splat][0]
      @session = Session.load(path)
      @current_view = :transcript
      @back_path = "/evals"
      @back_label = "Evals"
      @header_title = eval_run_title(rel)
      @transcript_path = eval_run_url(rel)
      @story_path = eval_run_url(rel, suffix: "/story")
      erb :session
    end
  end
end
