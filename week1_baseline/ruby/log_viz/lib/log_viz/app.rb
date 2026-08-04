require "sinatra/base"
require "sinatra/reloader"
require "json"
require "time"
require "uri"

require_relative "session"
require_relative "eval_results"
require_relative "movement_results"
require_relative "world_map"
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
      # Which tab a specific run's log belongs under — looked up by its own
      # log_path rather than threaded through the URL, so /evals/runs/*
      # doesn't need a parallel /evals/runs/legacy/* route tree just to
      # know which "back" link to show. Same load_all() cost /evals itself
      # already pays per request; not worth caching for a local dev tool.
      def eval_run_legacy?(rel)
        run = EvalResults.load_all(settings.eval_results_dir).find { |r| r.log_path == rel }
        run ? run.legacy_scoring? : false
      end

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

      # Six-category identity encoding for the outcome bar chart (see
      # EvalResults::OUTCOME_ORDER / EvalRun#outcome_category) — different
      # in kind from EVAL_STATUS_COLOR above, which is a two-state pass/fail
      # status, not a "which of several reasons" identity. Order matches
      # OUTCOME_ORDER exactly (pass, never_connected, fabricated, timed_out,
      # out_of_budget, other_fail) and was picked from the project's
      # categorical palette (green/blue/orange/aqua/yellow/magenta slots),
      # then validated as an ordered adjacent-pair sequence with
      # scripts/validate_palette.js from the dataviz skill — reordering
      # these breaks that validation, so don't shuffle them without
      # re-running it. Three of the six (aqua/yellow/magenta) land below the
      # 3:1 surface-contrast floor, which the skill treats as a WARN, not a
      # FAIL, on the condition that a table view stays available as backup —
      # the existing per-run table below every chart already provides that.
      OUTCOME_COLORS = {
        pass: "#008300",
        never_connected: "#2a78d6",
        fabricated: "#eb6834",
        timed_out: "#1baf7a",
        out_of_budget: "#eda100",
        other_fail: "#e87ba4",
      }.freeze

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

      # Inline SVG stacked bar chart: one bar per EvalGroup (a model x mode
      # cell for one scenario — pass `groups` in the same order as the
      # heatmap above it renders its rows/columns, so scanning down the
      # heatmap and across this chart lines the two up). Segments stack in
      # EvalResults::OUTCOME_ORDER so failure *composition* is visible, not
      # just the pass rate the heatmap already shows — this is what actually
      # answers "track errors ... across all models" (bakery.py + score.py's
      # doc comments) rather than a second view of the same rate number.
      # Y axis is an absolute run count on purpose, not a percentage: n=3 and
      # n=30 look identical as a rate but very different as a bar height,
      # and that difference is exactly the kind of thing worth catching
      # before trusting a rate next to it. Bar slot width is fixed per group
      # (BAR_SLOT) rather than the chart's total width being fixed, since the
      # number of model x mode combinations grows as more get tested — wrap
      # the returned SVG in an overflow-x:auto container in the view.
      OUTCOME_BAR_SLOT = 72
      OUTCOME_CHART_MIN_WIDTH = 360

      def outcome_bar_chart(groups, height: 300)
        groups = groups.reject { |g| g.run_count.zero? }
        return "" if groups.empty?

        pad = { left: 42, right: 16, top: 20, bottom: 90 }
        plot_w = [groups.length * OUTCOME_BAR_SLOT, OUTCOME_CHART_MIN_WIDTH].max
        width = pad[:left] + plot_w + pad[:right]
        plot_h = height - pad[:top] - pad[:bottom]

        bar_w = [OUTCOME_BAR_SLOT - 16, 12].max
        max_total = [groups.map(&:run_count).max, 1].max

        y_of = ->(v) { (pad[:top] + plot_h - (v.to_f / max_total) * plot_h).round(1) }

        grid = (0..4).map do |i|
          yt = (max_total * i / 4.0).round
          y = y_of.call(yt)
          %(<line class="outcome-grid" x1="#{pad[:left]}" y1="#{y}" x2="#{pad[:left] + plot_w}" y2="#{y}"/>) +
            %(<text class="outcome-tick" x="#{pad[:left] - 6}" y="#{y + 3}" text-anchor="end">#{yt}</text>)
        end.join

        bars = groups.each_with_index.map do |g, i|
          slot_x = pad[:left] + (i * OUTCOME_BAR_SLOT)
          x = (slot_x + (OUTCOME_BAR_SLOT - bar_w) / 2.0).round(1)
          counts = g.outcome_counts
          running = 0
          segments = EvalResults::OUTCOME_ORDER.filter_map do |cat|
            n = counts[cat]
            next if n.zero?

            y_top = y_of.call(running + n)
            y_bottom = y_of.call(running)
            running += n
            # 2px surface gap between stacked segments (dataviz skill's mark spec).
            seg_h = [y_bottom - y_top - 2, 0].max
            label = "#{EvalResults::OUTCOME_LABELS[cat]}: #{n} — #{g.model_label} / #{g.mode}"
            %(<rect class="outcome-seg" x="#{x}" y="#{y_top.round(1)}" width="#{bar_w}" height="#{seg_h.round(1)}" fill="#{OUTCOME_COLORS[cat]}"><title>#{text_html(label)}</title></rect>)
          end.join

          label_x = (x + bar_w / 2.0).round(1)
          total_label = %(<text class="outcome-total" x="#{label_x}" y="#{pad[:top] - 6}" text-anchor="middle">#{g.run_count}</text>)
          tick_y = pad[:top] + plot_h + 12
          axis_label = %(<text class="outcome-axis-tick" x="#{label_x}" y="#{tick_y}" text-anchor="end" transform="rotate(-40 #{label_x} #{tick_y})">#{text_html("#{g.model_label} · #{g.mode}")}</text>)

          segments + total_label + axis_label
        end.join

        <<~SVG
          <svg class="outcome-chart" viewBox="0 0 #{width} #{height}" width="#{width}" height="#{height}" role="img" aria-label="run outcome breakdown by model and mode, stacked by pass or failure reason">
            #{grid}
            <line class="outcome-axis" x1="#{pad[:left]}" y1="#{pad[:top]}" x2="#{pad[:left]}" y2="#{pad[:top] + plot_h}"/>
            <line class="outcome-axis" x1="#{pad[:left]}" y1="#{pad[:top] + plot_h}" x2="#{pad[:left] + plot_w}" y2="#{pad[:top] + plot_h}"/>
            <text class="outcome-axis-label" x="12" y="#{pad[:top] + plot_h / 2}" text-anchor="middle" transform="rotate(-90 12 #{pad[:top] + plot_h / 2})">runs</text>
            #{bars}
          </svg>
        SVG
      end

      # Simple 2-category grouped bar chart — pass count and fail count side
      # by side per model, summed across every scenario and mode (see
      # EvalResults::ModelPassFail / pass_fail_by_model). Distinct from
      # outcome_bar_chart above: that one facets by scenario and breaks
      # failures into 6 reasons; this is the coarse "which models are
      # actually winning" view requested separately — no attempt to filter
      # out which scenario a pass came from, by design. Reuses
      # EVAL_STATUS_COLOR (the same pass/fail status colors as the scatter
      # charts elsewhere on this page) rather than a new palette — it's the
      # same two-state status encoding, not a new category set.
      PASS_FAIL_BAR_SLOT = 90
      PASS_FAIL_CHART_MIN_WIDTH = 300

      def pass_fail_bar_chart(rows, height: 280)
        rows = rows.reject { |r| r.total.zero? }
        return "" if rows.empty?

        pad = { left: 42, right: 16, top: 20, bottom: 80 }
        plot_w = [rows.length * PASS_FAIL_BAR_SLOT, PASS_FAIL_CHART_MIN_WIDTH].max
        width = pad[:left] + plot_w + pad[:right]
        plot_h = height - pad[:top] - pad[:bottom]

        bar_w = 26
        bar_gap = 4
        max_count = [rows.flat_map { |r| [r.pass_count, r.fail_count] }.max, 1].max

        y_of = ->(v) { (pad[:top] + plot_h - (v.to_f / max_count) * plot_h).round(1) }

        grid = (0..4).map do |i|
          yt = (max_count * i / 4.0).round
          y = y_of.call(yt)
          %(<line class="outcome-grid" x1="#{pad[:left]}" y1="#{y}" x2="#{pad[:left] + plot_w}" y2="#{y}"/>) +
            %(<text class="outcome-tick" x="#{pad[:left] - 6}" y="#{y + 3}" text-anchor="end">#{yt}</text>)
        end.join

        bars = rows.each_with_index.map do |r, i|
          slot_x = pad[:left] + (i * PASS_FAIL_BAR_SLOT)
          group_w = (bar_w * 2) + bar_gap
          group_x = slot_x + ((PASS_FAIL_BAR_SLOT - group_w) / 2.0)
          pass_x = group_x.round(1)
          fail_x = (group_x + bar_w + bar_gap).round(1)

          pass_y = y_of.call(r.pass_count)
          fail_y = y_of.call(r.fail_count)
          base_y = pad[:top] + plot_h
          pass_h = (base_y - pass_y).round(1)
          fail_h = (base_y - fail_y).round(1)

          pass_rect = %(<rect class="outcome-seg" x="#{pass_x}" y="#{pass_y}" width="#{bar_w}" height="#{pass_h}" fill="#{EVAL_STATUS_COLOR[:pass]}"><title>#{text_html("Pass: #{r.pass_count} — #{r.model_label}")}</title></rect>)
          fail_rect = %(<rect class="outcome-seg" x="#{fail_x}" y="#{fail_y}" width="#{bar_w}" height="#{fail_h}" fill="#{EVAL_STATUS_COLOR[:fail]}"><title>#{text_html("Fail: #{r.fail_count} — #{r.model_label}")}</title></rect>)
          pass_label = r.pass_count.positive? ? %(<text class="outcome-total" x="#{(pass_x + bar_w / 2.0).round(1)}" y="#{pass_y - 4}" text-anchor="middle">#{r.pass_count}</text>) : ""
          fail_label = r.fail_count.positive? ? %(<text class="outcome-total" x="#{(fail_x + bar_w / 2.0).round(1)}" y="#{fail_y - 4}" text-anchor="middle">#{r.fail_count}</text>) : ""

          label_x = (group_x + group_w / 2.0).round(1)
          tick_y = base_y + 12
          axis_label = %(<text class="outcome-axis-tick" x="#{label_x}" y="#{tick_y}" text-anchor="end" transform="rotate(-40 #{label_x} #{tick_y})">#{text_html(r.model_label)}</text>)

          pass_rect + fail_rect + pass_label + fail_label + axis_label
        end.join

        <<~SVG
          <svg class="outcome-chart" viewBox="0 0 #{width} #{height}" width="#{width}" height="#{height}" role="img" aria-label="pass vs fail run counts by model, across every scenario and mode">
            #{grid}
            <line class="outcome-axis" x1="#{pad[:left]}" y1="#{pad[:top]}" x2="#{pad[:left]}" y2="#{pad[:top] + plot_h}"/>
            <line class="outcome-axis" x1="#{pad[:left]}" y1="#{pad[:top] + plot_h}" x2="#{pad[:left] + plot_w}" y2="#{pad[:top] + plot_h}"/>
            <text class="outcome-axis-label" x="12" y="#{pad[:top] + plot_h / 2}" text-anchor="middle" transform="rotate(-90 12 #{pad[:top] + plot_h / 2})">runs</text>
            #{bars}
          </svg>
        SVG
      end

      def fmt_duration(seconds)
        s = seconds.to_i
        return "0s" if s <= 0

        s < 60 ? "#{s}s" : "#{s / 60}m #{s % 60}s"
      end

      # Force-directed layout (Fruchterman-Reingold) for one session's
      # visited rooms, derived purely from that session's own move
      # transitions — not resolved against CircleMUD's authoritative room
      # graph (vnums/exits, which would need the Python-only .wld parser).
      # So positions aren't comparable session-to-session; two runs that
      # visited the same rooms lay them out differently. Good enough for
      # "trace this one run's own path", the only thing the movement view
      # needs — a shared cross-session map is a separate, bigger feature.
      # Initial placement is a deterministic circle (index/count), so no RNG
      # seeding is needed for reproducible re-renders.
      def movement_layout(rooms, edges, width: 640, height: 460)
        return {} if rooms.empty?
        return { rooms.first => [width / 2.0, height / 2.0] } if rooms.length == 1

        pos = rooms.each_with_index.to_h do |room, i|
          angle = 2 * Math::PI * i / rooms.length
          [room, [width / 2.0 + (Math.cos(angle) * 140), height / 2.0 + (Math.sin(angle) * 140)]]
        end

        k = Math.sqrt((width * height).to_f / rooms.length)

        120.times do |iter|
          disp = Hash.new { |h, r| h[r] = [0.0, 0.0] }

          rooms.each do |a|
            rooms.each do |b|
              next if a == b

              dx = pos[a][0] - pos[b][0]
              dy = pos[a][1] - pos[b][1]
              dist = [Math.sqrt((dx * dx) + (dy * dy)), 0.01].max
              force = (k * k) / dist
              disp[a][0] += (dx / dist) * force
              disp[a][1] += (dy / dist) * force
            end
          end

          edges.each do |a, b|
            next unless pos[a] && pos[b]

            dx = pos[a][0] - pos[b][0]
            dy = pos[a][1] - pos[b][1]
            dist = [Math.sqrt((dx * dx) + (dy * dy)), 0.01].max
            force = (dist * dist) / k
            disp[a][0] -= (dx / dist) * force
            disp[a][1] -= (dy / dist) * force
            disp[b][0] += (dx / dist) * force
            disp[b][1] += (dy / dist) * force
          end

          temp = width * (1.0 - (iter.to_f / 120)) * 0.04
          rooms.each do |r|
            dx, dy = disp[r]
            dist = [Math.sqrt((dx * dx) + (dy * dy)), 0.01].max
            move = [dist, temp].min
            pos[r][0] = (pos[r][0] + ((dx / dist) * move)).clamp(40, width - 40)
            pos[r][1] = (pos[r][1] + ((dy / dist) * move)).clamp(40, height - 40)
          end
        end

        pos
      end

      MOVEMENT_ROOM_R_MIN = 7
      MOVEMENT_ROOM_R_MAX = 20

      def movement_room_radius(dwell_s, max_dwell_s)
        return MOVEMENT_ROOM_R_MIN if max_dwell_s.to_f <= 0

        frac = (dwell_s.to_f / max_dwell_s).clamp(0.0, 1.0)
        (MOVEMENT_ROOM_R_MIN + (frac * (MOVEMENT_ROOM_R_MAX - MOVEMENT_ROOM_R_MIN))).round(1)
      end

      # The static map: room nodes sized/filled by total dwell time (reuses
      # heatmap_fill's sequential blue ramp — dwell is a magnitude like its
      # other callers, not a category) with the traveled path drawn over
      # them in visit order. `with_player` adds an empty #player-dot circle
      # that movement.erb's script repositions during playback, so the
      # static overview and the interactive player share one layout instead
      # of computing it twice.
      # Rough average glyph width for this app's sans-serif UI font, as a
      # fraction of font-size — not exact (no proportional font is), just
      # enough to estimate a label's bounding box for collision checks
      # below. A little generous on purpose: overestimating width means
      # false-positive "collisions" (a label gets skipped that would
      # actually have fit), which is a far better failure mode than
      # underestimating and rendering overlapping text anyway.
      LABEL_CHAR_WIDTH = 0.6

      # Greedy label placement shared by movement_map_svg and
      # movement_world_heatmap_svg — both draw a node-link room graph and
      # both were, before this, placing every label dead-center above its
      # node with no awareness of any *other* label, which collided
      # constantly wherever two rooms sat close together (a common case:
      # force-directed layout naturally pulls connected rooms close).
      #
      # `candidates` is an array of {key:, text:, x:, y:, r:}, already in
      # priority order (caller decides — busiest room first is typical, so
      # a crowded map's most important labels are the ones that win a
      # spot). For each candidate this tries a fixed set of positions
      # around its node (above, below, right, left) and takes the first
      # that (a) stays inside the canvas and (b) doesn't overlap any
      # label already placed; if none of the four work, that label is
      # skipped entirely rather than rendered on top of something else —
      # the room still gets its node, its hover tooltip, and its table row
      # elsewhere, so nothing is actually lost, just not labeled inline.
      #
      # Returns {key => {x:, y:, anchor:}}; a key with no entry was skipped.
      def place_labels(candidates, width:, height:, font_size:)
        placed_boxes = []
        result = {}

        candidates.each do |c|
          text_w = (c[:text].length * font_size * LABEL_CHAR_WIDTH) + 2
          text_h = font_size * 1.3
          gap = c[:r] + 4

          tries = [
            { x: c[:x], y: c[:y] - gap, anchor: "middle" },
            { x: c[:x], y: c[:y] + gap + text_h, anchor: "middle" },
            { x: c[:x] + gap, y: c[:y] + (text_h / 3), anchor: "start" },
            { x: c[:x] - gap, y: c[:y] + (text_h / 3), anchor: "end" },
          ]

          tries.each do |t|
            box = case t[:anchor]
                  when "middle" then [t[:x] - (text_w / 2), t[:y] - text_h, t[:x] + (text_w / 2), t[:y]]
                  when "start"  then [t[:x], t[:y] - text_h, t[:x] + text_w, t[:y]]
                  when "end"    then [t[:x] - text_w, t[:y] - text_h, t[:x], t[:y]]
                  end
            next if box[0].negative? || box[1].negative? || box[2] > width || box[3] > height
            next if placed_boxes.any? { |p| box[0] < p[2] && box[2] > p[0] && box[1] < p[3] && box[3] > p[1] }

            result[c[:key]] = { x: t[:x].round(1), y: t[:y].round(1), anchor: t[:anchor] }
            placed_boxes << box
            break
          end
        end

        result
      end

      # label_top_n: nil labels every room (the single-session view's
      # default — canvas is 640×460 and most sessions visit a few dozen
      # rooms at most, so crowding is rare there). /movement/grid's panels
      # are a fraction of that size and can hold a dozen+ rooms, where
      # labeling every node just overlaps into noise — passing a small N
      # there keeps only the busiest rooms' text, same "label selectively"
      # call the world heatmap already makes for the same reason.
      def movement_map_svg(positions, edges, room_stats, segments, width: 640, height: 460, with_player: false, label_top_n: nil, label_font_size: 9)
        return "" if positions.empty?

        max_dwell = room_stats.map { |r| r[:dwell_s] }.max.to_f
        stats_by_room = room_stats.each_with_object({}) { |r, h| h[r[:room]] = r }
        ranked = room_stats.sort_by { |r| -r[:dwell_s] }
        ranked = ranked.first(label_top_n) if label_top_n

        label_candidates = ranked.filter_map do |stat|
          x, y = positions[stat[:room]]
          next unless x

          r = movement_room_radius(stat[:dwell_s], max_dwell)
          { key: stat[:room], text: stat[:room], x: x, y: y, r: r }
        end
        label_positions = place_labels(label_candidates, width: width, height: height, font_size: label_font_size)

        edge_lines = edges.filter_map do |a, b|
          next unless positions[a] && positions[b]

          ax, ay = positions[a]
          bx, by = positions[b]
          %(<line class="move-edge" x1="#{ax}" y1="#{ay}" x2="#{bx}" y2="#{by}"/>)
        end.join

        path_points = segments.filter_map { |seg| positions[seg.room] }
        path = if path_points.length > 1
                 %(<polyline class="move-path" points="#{path_points.map { |x, y| "#{x},#{y}" }.join(' ')}"/>)
               else
                 ""
               end

        nodes = positions.map do |room, (x, y)|
          stat = stats_by_room[room] || { dwell_s: 0.0, visits: 0 }
          r = movement_room_radius(stat[:dwell_s], max_dwell)
          fill = heatmap_fill(max_dwell.positive? ? stat[:dwell_s] / max_dwell : nil)
          title = "#{room} — #{fmt_duration(stat[:dwell_s])}, #{stat[:visits]} visit#{'s' unless stat[:visits] == 1}"
          pos = label_positions[room]
          label = pos ? %(<text class="move-room-label" x="#{pos[:x]}" y="#{pos[:y]}" text-anchor="#{pos[:anchor]}" font-size="#{label_font_size}">#{text_html(room)}</text>) : ""
          <<~SVG
            <g class="move-room" data-room-id="#{anchor_slug('room', room)}">
              <circle cx="#{x}" cy="#{y}" r="#{r}" fill="#{fill}"><title>#{text_html(title)}</title></circle>
              #{label}
            </g>
          SVG
        end.join

        start_xy = positions[segments.first&.room]
        player = with_player && start_xy ? %(<circle id="player-dot" class="player-dot" r="9" cx="#{start_xy[0]}" cy="#{start_xy[1]}"/>) : ""

        <<~SVG
          <svg class="move-map" viewBox="0 0 #{width} #{height}" role="img" aria-label="room-to-room path taken during this session">
            #{edge_lines}
            #{path}
            #{nodes}
            #{player}
          </svg>
        SVG
      end

      # segments + each room's screen position, as the JSON blob
      # movement.erb's playback script reads — plain elapsed-seconds floats
      # (start/duration relative to session start) rather than ISO
      # timestamps, so the client never has to parse dates or think about
      # timezones, just add numbers.
      def movement_trace_json(segments, positions)
        segments.map do |seg|
          x, y = positions[seg.room]
          {
            room: seg.room, room_id: anchor_slug("room", seg.room), visit_index: seg.visit_index,
            start: seg.start_offset_s.to_f.round(2), duration: seg.duration_s.to_f.round(2),
            blocked: seg.blocked_count, looks: seg.look_count, x: x, y: y,
          }
        end.to_json.gsub("</", '<\/')
      end

      # ---- cross-session movement comparison (/movement, /movement/replay) ----

      # The dataviz skill's validated 8-slot categorical theme (see
      # references/palette.md — same source OUTCOME_COLORS above already
      # draws from), reused unmodified rather than re-ordered/re-validated:
      # this is a different categorical dimension (model identity, not
      # outcome), so a fresh assignment off the same passing order is the
      # documented way to onboard a new series set, not a new palette.
      MOVEMENT_MODEL_COLORS = %w[#2a78d6 #eb6834 #1baf7a #eda100 #e87ba4 #008300 #4a3aa7 #e34948].freeze

      # A model keeps the same color everywhere it appears — assigned from
      # the FULL set of models in the dataset, alphabetically, never from
      # whatever subset one particular chart/scenario happens to be
      # showing. That's what "color follows the entity, never its rank"
      # requires: filtering to one scenario must not repaint the models
      # that remain. Beyond 8 models (today's dataset has 3) the extras
      # share the last slot rather than generating new hues — the
      # documented "fold to Other" behavior past a validated palette's cap.
      def movement_model_colors(all_model_labels)
        sorted = all_model_labels.uniq.sort
        sorted.each_with_index.to_h { |label, i| [label, MOVEMENT_MODEL_COLORS[[i, MOVEMENT_MODEL_COLORS.length - 1].min]] }
      end

      MOVEMENT_BAR_SLOT = 90
      MOVEMENT_BAR_MIN_WIDTH = 300

      # One bar per model for a single scalar (avg blocked moves, avg rooms
      # explored, ...) — same shape as pass_fail_bar_chart/outcome_bar_chart
      # above, parameterized over the metric since the scoreboard needs this
      # exact chart twice for two different fields. `value` is called with
      # each MovementResults::ModelSummary.
      def movement_avg_bar_chart(summaries, colors, y_label:, height: 260, &value)
        rows = summaries.reject { |s| s.run_count.zero? }.sort_by { |s| -value.call(s) }
        return "" if rows.empty?

        pad = { left: 42, right: 16, top: 20, bottom: 90 }
        plot_w = [rows.length * MOVEMENT_BAR_SLOT, MOVEMENT_BAR_MIN_WIDTH].max
        width = pad[:left] + plot_w + pad[:right]
        plot_h = height - pad[:top] - pad[:bottom]

        bar_w = 30
        max_v = [rows.map { |s| value.call(s) }.max, 0.01].max
        y_of = ->(v) { (pad[:top] + plot_h - (v / max_v * plot_h)).round(1) }

        grid = (0..4).map do |i|
          yt = max_v * i / 4.0
          y = y_of.call(yt)
          %(<line class="outcome-grid" x1="#{pad[:left]}" y1="#{y}" x2="#{pad[:left] + plot_w}" y2="#{y}"/>) +
            %(<text class="outcome-tick" x="#{pad[:left] - 6}" y="#{y + 3}" text-anchor="end">#{yt.round(1)}</text>)
        end.join

        bars = rows.each_with_index.map do |s, i|
          v = value.call(s)
          slot_x = pad[:left] + (i * MOVEMENT_BAR_SLOT)
          x = (slot_x + ((MOVEMENT_BAR_SLOT - bar_w) / 2.0)).round(1)
          y_top = y_of.call(v)
          base_y = pad[:top] + plot_h
          h = [(base_y - y_top).round(1), 0].max
          label = "#{s.model_label}: #{v.round(2)} — #{s.run_count} run#{'s' unless s.run_count == 1}"
          rect = %(<rect class="outcome-seg" x="#{x}" y="#{y_top}" width="#{bar_w}" height="#{h}" fill="#{colors[s.model_label]}"><title>#{text_html(label)}</title></rect>)
          val_label = %(<text class="outcome-total" x="#{(x + (bar_w / 2.0)).round(1)}" y="#{y_top - 4}" text-anchor="middle">#{v.round(1)}</text>)
          label_x = (x + (bar_w / 2.0)).round(1)
          tick_y = base_y + 12
          axis_label = %(<text class="outcome-axis-tick" x="#{label_x}" y="#{tick_y}" text-anchor="end" transform="rotate(-40 #{label_x} #{tick_y})">#{text_html(s.model_label)}</text>)
          rect + val_label + axis_label
        end.join

        <<~SVG
          <svg class="outcome-chart" viewBox="0 0 #{width} #{height}" width="#{width}" height="#{height}" role="img" aria-label="#{text_html(y_label)}, by model">
            #{grid}
            <line class="outcome-axis" x1="#{pad[:left]}" y1="#{pad[:top]}" x2="#{pad[:left]}" y2="#{pad[:top] + plot_h}"/>
            <line class="outcome-axis" x1="#{pad[:left]}" y1="#{pad[:top] + plot_h}" x2="#{pad[:left] + plot_w}" y2="#{pad[:top] + plot_h}"/>
            <text class="outcome-axis-label" x="12" y="#{pad[:top] + plot_h / 2}" text-anchor="middle" transform="rotate(-90 12 #{pad[:top] + plot_h / 2})">#{text_html(y_label)}</text>
            #{bars}
          </svg>
        SVG
      end

      # Multi-series line chart: one polyline per model, x = real elapsed
      # time (each batch's actual date, not ordinal position — batches
      # aren't evenly spaced), y = the given metric. A model only gets
      # points for the batches it actually ran in, so series lengths
      # differ — a real gap, not padded to line up. Legend is mandatory
      # (2+ series almost always here); per-point <title> stands in for a
      # hover tooltip, same convention as scatter_plot above.
      def movement_trend_chart(trend_by_model, colors, y_label:, width: 700, height: 300, &value)
        points = trend_by_model.values.flatten
        return "" if points.length < 2

        pad = { left: 46, right: 16, top: 16, bottom: 34 }
        plot_w = width - pad[:left] - pad[:right]
        plot_h = height - pad[:top] - pad[:bottom]

        min_date = points.map(&:date).min
        span = [points.map(&:date).max - min_date, 1].max
        max_v = [points.map { |p| value.call(p) }.max, 0.01].max

        x_of = ->(d) { (pad[:left] + ((d - min_date) / span * plot_w)).round(1) }
        y_of = ->(v) { (pad[:top] + plot_h - (v / max_v * plot_h)).round(1) }

        grid = (0..4).map do |i|
          yt = max_v * i / 4.0
          y = y_of.call(yt)
          %(<line class="outcome-grid" x1="#{pad[:left]}" y1="#{y}" x2="#{pad[:left] + plot_w}" y2="#{y}"/>) +
            %(<text class="outcome-tick" x="#{pad[:left] - 6}" y="#{y + 3}" text-anchor="end">#{yt.round(1)}</text>)
        end.join

        series = trend_by_model.sort.map do |model, model_points|
          next "" if model_points.empty?

          color = colors[model]
          coords = model_points.map { |p| [x_of.call(p.date), y_of.call(value.call(p))] }
          line = %(<polyline class="trend-line" points="#{coords.map { |x, y| "#{x},#{y}" }.join(' ')}" stroke="#{color}"/>)
          dots = model_points.zip(coords).map do |p, (x, y)|
            label = "#{model}: #{value.call(p).round(2)} — batch #{p.batch_id}, #{p.run_count} run#{'s' unless p.run_count == 1}"
            %(<circle class="trend-dot" cx="#{x}" cy="#{y}" r="4" fill="#{color}"><title>#{text_html(label)}</title></circle>)
          end.join
          line + dots
        end.join

        <<~SVG
          <svg class="scatter" viewBox="0 0 #{width} #{height}" role="img" aria-label="#{text_html(y_label)} over time, by model">
            #{grid}
            <line class="scatter-axis" x1="#{pad[:left]}" y1="#{pad[:top]}" x2="#{pad[:left]}" y2="#{pad[:top] + plot_h}"/>
            <line class="scatter-axis" x1="#{pad[:left]}" y1="#{pad[:top] + plot_h}" x2="#{pad[:left] + plot_w}" y2="#{pad[:top] + plot_h}"/>
            <text class="scatter-axis-label" x="12" y="#{pad[:top] + plot_h / 2}" text-anchor="middle" transform="rotate(-90 12 #{pad[:top] + plot_h / 2})">#{text_html(y_label)}</text>
            #{series}
          </svg>
        SVG
      end

      def movement_legend(model_labels, colors)
        model_labels.sort.map do |m|
          %(<span class="trend-legend-item"><span class="trend-legend-dot" style="background:#{colors[m]}"></span>#{text_html(m)}</span>)
        end.join
      end

      # The shared map for /movement/replay: room nodes only, no per-model
      # markers — this is a *group* heat trail (see movement_replay.erb's
      # script), not individual dots, so identity lives in the readout
      # table below the map, not on the map itself. Each node's fill starts
      # neutral gray and is overwritten client-side every frame by how many
      # models are currently (or recently) in that room, using the same
      # sequential blue ramp as heatmap_fill — data-vnum is what the script
      # uses to find each node.
      def movement_replay_map_svg(positions, edges, world_map, width: 700, height: 480)
        return "" if positions.empty?

        edge_lines = edges.filter_map do |a, b|
          next unless positions[a] && positions[b]

          ax, ay = positions[a]
          bx, by = positions[b]
          %(<line class="move-edge" x1="#{ax}" y1="#{ay}" x2="#{bx}" y2="#{by}"/>)
        end.join

        nodes = positions.map do |vnum, (x, y)|
          name = world_map.name_for(vnum)
          <<~SVG
            <g class="move-room" data-vnum="#{vnum}">
              <circle cx="#{x}" cy="#{y}" r="8" fill="#{heatmap_fill(nil)}"><title>#{text_html(name)}</title></circle>
              <text class="move-room-label" x="#{x}" y="#{y - 12}" text-anchor="middle">#{text_html(name)}</text>
            </g>
          SVG
        end.join

        <<~SVG
          <svg id="movement-replay-map" class="move-map" viewBox="0 0 #{width} #{height}" role="img" aria-label="shared room map, glowing by how many models are currently or recently in each room">
            #{edge_lines}
            #{nodes}
          </svg>
        SVG
      end

      # One model's resolved (vnum -> position) trace as the replay
      # script's JSON, keyed by model_label. Segments whose room name never
      # resolved to a vnum (see WorldMap#resolve_trace) are dropped rather
      # than guessed at — that gap just can't contribute heat to any room,
      # and the per-model readout says so explicitly rather than going
      # silently blank.
      def movement_replay_json(runs_by_model, positions)
        runs_by_model.each_with_object({}) do |(model, data), h|
          points = data[:row].trace.zip(data[:vnums]).filter_map do |seg, vnum|
            next unless vnum && positions[vnum]

            x, y = positions[vnum]
            { room: seg.room, vnum: vnum, start: seg.start_offset_s.to_f.round(2),
              duration: seg.duration_s.to_f.round(2), x: x, y: y }
          end
          h[model] = { id: anchor_slug("model", model), points: points }
        end.to_json.gsub("</", '<\/')
      end

      # HEATMAP_BLUE_STEPS as JSON for the replay script's client-side heat
      # color — same reasoning as outcome_categories/outcome_label above
      # for why views go through an accessor rather than reaching the
      # constant directly.
      def heatmap_ramp_json = HEATMAP_BLUE_STEPS.to_json

      # Trace-time seconds a room keeps glowing in /movement/replay after
      # the last model standing in it moves on — both the page's own copy
      # and its playback script read this same value, so they can't drift
      # apart the way two independently-chosen numbers eventually would.
      MOVEMENT_HEAT_DECAY_S = 20
      def movement_heat_decay_s = MOVEMENT_HEAT_DECAY_S

      # /movement/grid's per-panel canvas — deliberately small (the single-
      # session view's own map is 640×460) since the point of this page is
      # fitting several side by side at once, not reading one in detail.
      # Both the route (movement_layout's coordinate space) and the view
      # (movement_map_svg's viewBox) need the same numbers, so this is the
      # one place either can drift from.
      MOVEMENT_GRID_PANEL_W = 190
      MOVEMENT_GRID_PANEL_H = 150
      def movement_grid_panel_w = MOVEMENT_GRID_PANEL_W
      def movement_grid_panel_h = MOVEMENT_GRID_PANEL_H

      MOVEMENT_WORLD_LABEL_TOP_N = 15

      # The static /movement/world heatmap: every visited room from the
      # (possibly filtered) run set, fixed size, filled by the chosen
      # metric's fraction of the busiest room. Unlike the single-session
      # map (movement_map_svg, ~10 rooms) or one scenario's replay map
      # (movement_replay_map_svg, ~dozens), this spans every scenario at
      # once — 90+ rooms in the current dataset — so labeling every node
      # the way those two do would just be ink-on-ink. Per the dataviz
      # skill's "label selectively, never every point" rule, only the
      # MOVEMENT_WORLD_LABEL_TOP_N busiest rooms get a direct text label;
      # every room still gets a hover <title> and a row in the table below
      # the chart, so nothing is actually hidden — just not labeled inline.
      def movement_world_heatmap_svg(positions, edges, traffic, world_map, metric:, width: 900, height: 640)
        return "" if positions.empty?

        by_vnum = traffic.each_with_object({}) { |t, h| h[t.vnum] = t }
        max_v = traffic.map { |t| t[metric] }.max.to_f
        ranked = traffic.sort_by { |t| -t[metric] }.first(MOVEMENT_WORLD_LABEL_TOP_N)

        label_candidates = ranked.filter_map do |t|
          x, y = positions[t.vnum]
          next unless x

          { key: t.vnum, text: world_map.name_for(t.vnum), x: x, y: y, r: movement_room_radius(t[metric], max_v) }
        end
        label_positions = place_labels(label_candidates, width: width, height: height, font_size: 9)

        edge_lines = edges.filter_map do |a, b|
          next unless positions[a] && positions[b]

          ax, ay = positions[a]
          bx, by = positions[b]
          %(<line class="move-edge" x1="#{ax}" y1="#{ay}" x2="#{bx}" y2="#{by}"/>)
        end.join

        nodes = positions.map do |vnum, (x, y)|
          t = by_vnum[vnum]
          name = world_map.name_for(vnum)
          frac = max_v.positive? ? t[metric] / max_v : nil
          r = movement_room_radius(t[metric], max_v)
          label_text = "#{name} — #{fmt_duration(t.dwell_s)} across #{t.visits} visit#{'s' unless t.visits == 1} in #{t.run_count} run#{'s' unless t.run_count == 1}"
          pos = label_positions[vnum]
          label = pos ? %(<text class="move-room-label" x="#{pos[:x]}" y="#{pos[:y]}" text-anchor="#{pos[:anchor]}">#{text_html(name)}</text>) : ""
          <<~SVG
            <g class="move-room">
              <circle cx="#{x}" cy="#{y}" r="#{r}" fill="#{heatmap_fill(frac)}"><title>#{text_html(label_text)}</title></circle>
              #{label}
            </g>
          SVG
        end.join

        <<~SVG
          <svg class="move-map" viewBox="0 0 #{width} #{height}" role="img" aria-label="whole-world heatmap of room traffic across every eval run">
            #{edge_lines}
            #{nodes}
          </svg>
        SVG
      end

      # /movement/grid's shared-step data, one entry per panel. Each point
      # already carries its room_id (same anchor_slug scheme
      # movement_map_svg's own <g data-room-id> uses) so the script can
      # highlight the right node in that panel's own SVG without
      # recomputing the slug or relying on x/y float equality.
      def movement_grid_json(panels)
        panels.map do |p|
          points = p[:trace].map do |seg|
            x, y = p[:positions][seg.room]
            { room: seg.room, room_id: anchor_slug("room", seg.room), index: seg.visit_index, x: x, y: y }
          end
          { model: p[:model], id: anchor_slug("model", p[:model]), points: points }
        end.to_json.gsub("</", '<\/')
      end

      # URL-fragment-safe id from arbitrary scenario/model/mode strings
      # (which contain colons, slashes, dots, spaces — none valid bare in an
      # HTML id/href fragment). Used by the /evals TOC and each collapsible
      # group section's anchor — same slug-building logic in both places so
      # a TOC link always actually lands on its target.
      def anchor_slug(*parts)
        parts.join("-").downcase.gsub(/[^a-z0-9]+/, "-").gsub(/-+/, "-").gsub(/\A-|-\z/, "")
      end

      # Thin accessors so evals.erb (the legend) doesn't reference
      # LogViz::EvalResults's constants directly — an ERB template compiles
      # to a method on LogViz::App, which doesn't share app.rb's own lexical
      # nesting inside `module LogViz`, so a bare EvalResults::OUTCOME_ORDER
      # in the view raises NameError even though the identical reference
      # works fine here in app.rb itself. Same reasoning as every other
      # piece of chart styling already being a helper method rather than a
      # constant the view reaches into directly (heatmap_fill, scatter_plot).
      def outcome_categories = EvalResults::OUTCOME_ORDER
      def outcome_label(category) = EvalResults::OUTCOME_LABELS[category]
      def outcome_color(category) = OUTCOME_COLORS[category]

      # Shared by both /sessions/:id/movement and /evals/runs/*/movement —
      # everything past "@session is loaded" is identical, so each route
      # only needs to set @session (and the eval route's back/nav vars)
      # before calling this.
      def render_movement
        @segments   = @session.movement_trace
        @rooms      = @segments.map(&:room).uniq
        @edges      = @session.movement_edges
        @positions  = movement_layout(@rooms, @edges)
        @room_stats = @session.movement_room_stats
        last = @segments.last
        @total_duration_s = last ? (last.start_offset_s.to_f + last.duration_s.to_f) : 0.0
        erb :movement
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

    # Room-by-room replay of a session's move/look trace (Session#movement_trace)
    # — a static path-over-map summary plus an interactive scrub/play control.
    # Same Session parsing every other view uses; this just adds a layout pass
    # (movement_layout) over the rooms/edges it already exposes.
    get "/sessions/:id/movement" do
      id   = File.basename(params[:id])
      path = File.join(settings.sessions_dir, "#{id}.jsonl")
      halt 404, "Session not found: #{id}" unless File.file?(path)

      @session = Session.load(path)
      @current_view = :movement
      render_movement
    end

    get "/evals" do
      current, _legacy = EvalResults.partition_by_scoring(EvalResults.load_all(settings.eval_results_dir))
      @groups = EvalResults.groups(current)
      @heatmaps = EvalResults.heatmaps(@groups)
      @pass_fail_by_model = EvalResults.pass_fail_by_model(@groups)
      @legacy = false
      erb :evals
    end

    # Same view, but the pre-hardening pool on its own (see
    # EvalRun#current_scoring?) — runs scored before mud_connected/
    # content_matched existed, kept visible as a labeled "test set" rather
    # than either silently mixed into /evals or deleted outright.
    get "/evals/legacy" do
      _current, legacy = EvalResults.partition_by_scoring(EvalResults.load_all(settings.eval_results_dir))
      @groups = EvalResults.groups(legacy)
      @heatmaps = EvalResults.heatmaps(@groups)
      @pass_fail_by_model = EvalResults.pass_fail_by_model(@groups)
      @legacy = true
      erb :evals
    end

    # A model-vs-model leaderboard, separate from /evals's scenario/mode
    # drill-down — raw pass/fail counts summed across every scenario and
    # mode, ranked by win rate. New models need zero code changes to show
    # up here: it's a straight aggregation off whatever model_label strings
    # already exist in evals/results/*.jsonl, run through the same
    # groups()/leaderboard() pipeline /evals itself uses.
    get "/scoreboard" do
      current, _legacy = EvalResults.partition_by_scoring(EvalResults.load_all(settings.eval_results_dir))
      @groups = EvalResults.groups(current)
      @leaderboard = EvalResults.leaderboard(@groups)
      @legacy = false
      erb :scoreboard
    end

    get "/scoreboard/legacy" do
      _current, legacy = EvalResults.partition_by_scoring(EvalResults.load_all(settings.eval_results_dir))
      @groups = EvalResults.groups(legacy)
      @leaderboard = EvalResults.leaderboard(@groups)
      @legacy = true
      erb :scoreboard
    end

    # Cross-session movement comparison: current-scoring eval runs' own
    # Session#movement_trace, rolled up by model (see MovementResults). Only
    # runs whose harness actually logs a per-step transcript produce a row
    # at all (see MovementResults.for_runs) — today that's every Ollama/
    # boukensha run and none of the OpenCode ones, a real instrumentation
    # gap rather than a bug, and the view says so rather than showing a
    # misleading all-zero bar for the harness that has no data.
    get "/movement" do
      current, _legacy = EvalResults.partition_by_scoring(EvalResults.load_all(settings.eval_results_dir))
      @rows = MovementResults.for_runs(current, settings.eval_results_dir)
      @model_summaries = MovementResults.by_model(@rows)
      @model_colors = movement_model_colors(@rows.map(&:model_label))
      @scenario_modes = MovementResults.scenario_modes(@rows)

      default_key = @scenario_modes.first&.first
      @trend_scenario = params[:scenario] || default_key&.first
      @trend_mode     = params[:mode] || default_key&.last
      trend_rows = @rows.select { |r| r.scenario == @trend_scenario && r.mode == @trend_mode }
      @trend = MovementResults.trend_by_model(trend_rows)
      erb :movement_compare
    end

    # The most recent run per model, for one scenario+mode, replayed
    # together on one shared CircleMUD-derived map (WorldMap) instead of
    # each session's own ad-hoc per-run layout (see movement_layout above,
    # still used by the single-session /sessions/:id/movement view, which
    # has no cross-session positions to be consistent with).
    get "/movement/replay" do
      current, _legacy = EvalResults.partition_by_scoring(EvalResults.load_all(settings.eval_results_dir))
      rows = MovementResults.for_runs(current, settings.eval_results_dir)
      @scenario_modes = MovementResults.scenario_modes(rows)
      halt 404, "No movement data available" if @scenario_modes.empty?

      default_key = @scenario_modes.first.first
      @scenario = params[:scenario] || default_key.first
      @mode     = params[:mode] || default_key.last

      latest = MovementResults.latest_by_model(rows, scenario: @scenario, mode: @mode)
      @model_colors = movement_model_colors(rows.map(&:model_label))

      world = WorldMap.instance
      @runs_by_model = latest.transform_values { |row| { row: row, vnums: world.resolve_trace(row.room_names) } }
      vnums = @runs_by_model.values.flat_map { |d| d[:vnums] }.compact.uniq
      @edges = world.structural_edges(vnums)
      @positions = movement_layout(vnums, @edges, width: 700, height: 480)
      @world = world
      last_points = @runs_by_model.values.filter_map { |d| d[:row].trace.last }
      @total_duration_s = last_points.map { |s| s.start_offset_s.to_f + s.duration_s.to_f }.max.to_f
      erb :movement_replay
    end

    # Every current-scoring run's movement, from every scenario/mode/model
    # at once (unless narrowed via ?scenario=/?mode=), rolled up onto the
    # shared CircleMUD map as a static traffic heatmap — the "aggregation
    # of all results" view, as opposed to /movement/replay's one
    # scenario+mode played back live. No animation: hundreds of runs
    # spanning days have no one shared clock worth scrubbing, so this is a
    # single cumulative snapshot instead.
    get "/movement/world" do
      current, _legacy = EvalResults.partition_by_scoring(EvalResults.load_all(settings.eval_results_dir))
      rows = MovementResults.for_runs(current, settings.eval_results_dir)
      @scenario_modes = MovementResults.scenario_modes(rows)

      @scenario = params[:scenario]
      @mode = params[:mode]
      filtered = rows
      filtered = filtered.select { |r| r.scenario == @scenario } if @scenario
      filtered = filtered.select { |r| r.mode == @mode } if @mode
      @run_count = filtered.length

      world = WorldMap.instance
      @traffic, @resolved_segments, @total_segments = world.room_traffic(filtered)
      vnums = @traffic.map(&:vnum)
      @edges = world.structural_edges(vnums)
      @positions = movement_layout(vnums, @edges, width: 900, height: 640)
      @world = world
      @metric = params[:metric] == "visits" ? :visits : :dwell_s
      erb :movement_world
    end

    # Small multiples: each model's most recent run for one scenario+mode,
    # each drawn on its OWN ad-hoc layout (movement_layout, same as the
    # single-session view — not the shared WorldMap positions
    # /movement/replay and /movement/world use), side by side in a grid,
    # advanced together by a shared step counter instead of wall-clock
    # time. Steps are room arrivals (Segment#visit_index) rather than raw
    # MUD commands — this harness doesn't log a fixed per-command budget
    # the way a step-capped harness would, so "the Nth room visited" is the
    # closest analog that still means the same thing across models.
    get "/movement/grid" do
      current, _legacy = EvalResults.partition_by_scoring(EvalResults.load_all(settings.eval_results_dir))
      rows = MovementResults.for_runs(current, settings.eval_results_dir)
      @scenario_modes = MovementResults.scenario_modes(rows)
      halt 404, "No movement data available" if @scenario_modes.empty?

      default_key = @scenario_modes.first.first
      @scenario = params[:scenario] || default_key.first
      @mode     = params[:mode] || default_key.last

      latest = MovementResults.latest_by_model(rows, scenario: @scenario, mode: @mode)
      @model_colors = movement_model_colors(rows.map(&:model_label))

      @panels = latest.sort.map do |model, row|
        trace = row.trace
        room_names = trace.map(&:room).uniq
        edges = trace.each_cons(2).map { |a, b| [a.room, b.room] }.uniq
        positions = movement_layout(room_names, edges, width: MOVEMENT_GRID_PANEL_W, height: MOVEMENT_GRID_PANEL_H)
        {
          model: model,
          trace: trace,
          positions: positions,
          edges: edges,
          room_stats: Session.room_stats_for(trace),
        }
      end
      @max_steps = @panels.map { |p| p[:trace].length }.max.to_i
      erb :movement_grid
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
      legacy = eval_run_legacy?(rel)
      @back_path = legacy ? "/evals/legacy" : "/evals"
      @back_label = legacy ? "Evals (Legacy)" : "Evals"
      @header_title = eval_run_title(rel)
      @transcript_path = eval_run_url(rel)
      @story_path = eval_run_url(rel, suffix: "/story")
      @movement_path = eval_run_url(rel, suffix: "/movement")
      erb :story
    end

    get "/evals/runs/*/movement" do
      path = eval_run_log_path(params[:splat][0])
      halt 404, "Eval session log not found" unless path

      rel = params[:splat][0]
      @session = Session.load(path)
      @current_view = :movement
      legacy = eval_run_legacy?(rel)
      @back_path = legacy ? "/evals/legacy" : "/evals"
      @back_label = legacy ? "Evals (Legacy)" : "Evals"
      @header_title = eval_run_title(rel)
      @transcript_path = eval_run_url(rel)
      @story_path = eval_run_url(rel, suffix: "/story")
      @movement_path = eval_run_url(rel, suffix: "/movement")
      render_movement
    end

    get "/evals/runs/*" do
      path = eval_run_log_path(params[:splat][0])
      halt 404, "Eval session log not found" unless path

      rel = params[:splat][0]
      @session = Session.load(path)
      @current_view = :transcript
      legacy = eval_run_legacy?(rel)
      @back_path = legacy ? "/evals/legacy" : "/evals"
      @back_label = legacy ? "Evals (Legacy)" : "Evals"
      @header_title = eval_run_title(rel)
      @transcript_path = eval_run_url(rel)
      @story_path = eval_run_url(rel, suffix: "/story")
      @movement_path = eval_run_url(rel, suffix: "/movement")
      erb :session
    end
  end
end
