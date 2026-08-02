require "json"

module LogViz
  # One line of an evals/results/*.jsonl file — see evals/score.py's
  # score_run() for the exact fields. Deliberately thin: no parsing beyond
  # what the view needs, same spirit as Session wrapping the agent's own
  # phase-tagged JSONL rather than re-deriving it.
  EvalRun = Struct.new(:data) do
    def scenario = data["scenario"]
    def backend = data["backend"]
    def model = data["model"]
    # score_opencode.py's rows (run_bakery_opencode.py) have no "backend"
    # key at all — OpenCode's own --model is already a full "provider/model"
    # string, so there's nothing to prefix. Falling through to the plain
    # "#{backend}/#{model}" form for those would render a broken leading
    # slash ("/ollama/qwen3.6:35b-a3b") instead of a real label.
    def model_label = backend.to_s.empty? ? model.to_s : "#{backend}/#{model}"
    def success? = data["task_success"] == true
    # True when the agent wrote a non-empty output file whose content didn't
    # match the scenario's expected keywords — a real, observed failure mode
    # (a small model wrote a bar's menu to the bakery output path, having
    # admitted in its own summary it never found a bakery). Distinct from a
    # plain FAIL (no file at all) since it means the agent substituted
    # plausible-looking content instead of admitting it couldn't finish.
    def fabricated? = data["output_written"] == true && data["content_matched"] == false
    # False when the scorer found no successful authenticated MUD action in
    # the session log. Evidence may be an explicit mud_connect result or a
    # successful guard-protected gameplay tool after startup auto-connect.
    # nil means genuinely unknown for results written before this check.
    # This caught a model that invented a complete menu without connecting.
    def mud_connected?
      v = data["mud_connected"]
      v.nil? ? nil : v == true
    end
    def tool_call_count = data["tool_call_count"].to_i
    # Absent in results written before iteration tracking was added — treat
    # as unknown (nil) rather than 0, since 0 would misleadingly imply a
    # zero-iteration run instead of "not recorded".
    def iteration_count = data["iteration_count"]&.to_i
    def max_iterations = data["max_iterations"]&.to_i
    def duration_s = data["duration_s"].to_f
    def hit_turn_limit? = data["hit_turn_limit"] == true
    def process_failed? = data["process_failed"] == true
    def timed_out? = data["timed_out"] == true
    def batch_id = data["batch_id"]
    def repetition = data["repetition"]
    def log_path = data["log_path"]
    def working_dir = data["working_dir"]
    # "strict" (no reprompt) is the fallback for results written before
    # boukensha.run_reprompted() existed — they were all single-Agent-call
    # runs, i.e. equivalent to max_reprompts: 0.
    def mode = data["mode"] || "strict"
    def turn_count = data["turn_count"]&.to_i
    def reprompt_count = data["reprompt_count"]&.to_i
    def max_reprompts = data["max_reprompts"]&.to_i
    # nil for every result written before the OTel trace-id bridge existed,
    # and for any run where OTEL_EXPORTER_OTLP_ENDPOINT/the collector wasn't
    # reachable — _driver.py only prints TRACE_ID= when the span it opened
    # actually got a valid (non-no-op) context.
    def trace_id = data["trace_id"]

    # Mutually exclusive bucket for what happened, in priority order (most
    # fundamental blocker first) — a single run can match more than one flag
    # (a model that never connected AND got killed by the wall-clock timeout
    # before it could say so), so this picks one bucket per run for the
    # outcome chart rather than double-counting it across categories. Order
    # reflects how these actually chain in practice: a never-connected run
    # fabricating content is a consequence of not connecting, not a
    # coincidence alongside it — so never_connected outranks fabricated,
    # which outranks the generic timing/budget reasons.
    def outcome_category
      return :pass if success?
      return :never_connected if mud_connected? == false
      return :fabricated if fabricated?
      return :timed_out if timed_out?
      return :out_of_budget if hit_turn_limit?

      :other_fail
    end
    # A final `look` taken right after the trial ends (nil for older results,
    # and for a timed-out trial — SIGKILL doesn't allow _driver.py's own
    # cleanup code to run at all). Raw ANSI-colored MUD text — render with
    # ansi_html, don't escape/print plain. This is *where the trial left the
    # shared character*, not a scoring signal — see evals/README.md's "the
    # character's position isn't reset between trials" caveat for why that
    # matters for planning the next batch.
    def final_room = data["final_room"]
  end

  # A scenario+model+mode grouping with its runs, newest batch first — the
  # row unit the /evals dashboard actually displays. Strict and reprompt
  # runs of the same scenario/model land in separate groups on purpose:
  # they're different budgets, not directly comparable as one pool.
  # Aggregate stats are computed here rather than in the view so the ERB
  # stays display-only.
  EvalGroup = Struct.new(:scenario, :model_label, :mode, :runs) do
    def run_count = runs.length
    def success_count = runs.count(&:success?)
    def success_rate = run_count.zero? ? 0.0 : (success_count.to_f / run_count * 100)
    def avg_tool_calls = run_count.zero? ? 0.0 : runs.sum(&:tool_call_count).to_f / run_count
    def avg_duration_s = run_count.zero? ? 0.0 : runs.sum(&:duration_s) / run_count

    def runs_with_iterations = runs.select { |r| r.iteration_count && r.max_iterations&.positive? }
    def avg_iterations
      return nil if runs_with_iterations.empty?

      runs_with_iterations.sum(&:iteration_count).to_f / runs_with_iterations.length
    end
    def typical_max_iterations = runs_with_iterations.first&.max_iterations

    def runs_with_reprompts = runs.select { |r| r.reprompt_count }
    def avg_reprompts_used
      return nil if runs_with_reprompts.empty?

      runs_with_reprompts.sum(&:reprompt_count).to_f / runs_with_reprompts.length
    end

    def turn_limit_count = runs.count(&:hit_turn_limit?)
    def process_failed_count = runs.count(&:process_failed?)
    def fabricated_count = runs.count(&:fabricated?)
    def never_connected_count = runs.count { |r| r.mud_connected? == false }
    def last_batch_id = runs.map(&:batch_id).compact.max

    # {category => count} in OUTCOME_ORDER, every category present (0 rather
    # than absent) so the outcome chart can stack a fixed set of segments per
    # bar without a nil check per category.
    def outcome_counts
      EvalResults::OUTCOME_ORDER.to_h { |cat| [cat, runs.count { |r| r.outcome_category == cat }] }
    end
  end

  # One scenario's model x mode grid — models and modes are only the ones
  # that actually have at least one group, sorted so the heatmap reads left
  # (strict) to right (more reprompts) and top to bottom (alphabetical).
  # group_for returns nil for a combination with no runs yet, which the view
  # renders as an empty cell rather than a 0%-colored one — no data and
  # "0% success" are not the same thing.
  HeatmapScenario = Struct.new(:scenario, :models, :modes, :cells) do
    def group_for(model_label, mode) = cells[[model_label, mode]]
  end

  # Coarsest possible view: every task_success result for a model, summed
  # across every scenario and mode with no attempt to separate them out — a
  # return_to_midgaard recovery pass counts exactly the same as a bakery
  # pass here. Deliberately simpler than groups()/EvalGroup, which stay
  # scenario+mode-scoped for anywhere that distinction actually matters
  # (the heatmap, the outcome breakdown chart); this is the "which models
  # are actually winning, roughly" view, not a replacement for those.
  ModelPassFail = Struct.new(:model_label, :pass_count, :fail_count) do
    def total = pass_count + fail_count
    def win_rate = total.zero? ? 0.0 : (pass_count.to_f / total * 100)
  end

  module EvalResults
    # Fixed order, never reordered by count/rank — see EvalRun#outcome_category
    # for what puts a run in each bucket. Drives both the stacked-bar chart's
    # segment stacking order and its color assignment (app.rb's
    # OUTCOME_COLORS, same index order) — a categorical identity encoding,
    # not a magnitude one, so the order has to stay fixed for color to mean
    # the same thing across every bar and every render.
    OUTCOME_ORDER = %i[pass never_connected fabricated timed_out out_of_budget other_fail].freeze
    OUTCOME_LABELS = {
      pass: "Pass",
      never_connected: "Never connected",
      fabricated: "Fabricated content",
      timed_out: "Timed out",
      out_of_budget: "Out of budget",
      other_fail: "Other fail",
    }.freeze

    def self.load_all(results_dir)
      Dir.glob(File.join(results_dir, "*.jsonl")).sort.flat_map do |path|
        File.readlines(path).filter_map do |line|
          line = line.strip
          next if line.empty?

          EvalRun.new(JSON.parse(line))
        rescue JSON::ParserError
          nil # a line written mid-flush by a killed/timed-out trial
        end
      end
    end

    # Groups by [scenario, model_label, mode] — strict mode before reprompt
    # mode within the same scenario/model, so the dashboard reads "budget"
    # then "budget + reprompting". Each group's own runs are newest batch
    # first (see EvalGroup.new below).
    def self.groups(runs)
      runs
        .group_by { |r| [r.scenario, r.model_label, r.mode] }
        .map do |(scenario, model_label, mode), group_runs|
          EvalGroup.new(scenario, model_label, mode, group_runs.sort_by { |r| [r.batch_id.to_s, r.repetition.to_i] }.reverse)
        end
        .sort_by { |g| [g.scenario, g.model_label, *mode_sort_key(g.mode)] }
    end

    # "strict" first, then reprompt0 < reprompt2 < reprompt5 by the actual
    # number (not alphabetically, where "reprompt10" would sort before
    # "reprompt2") — extracted straight from the mode string rather than
    # threading max_reprompts through separately, since that's already the
    # single source of truth boukensha_agent.py encodes it into.
    def self.mode_sort_key(mode)
      return [0, 0] if mode == "strict"

      [1, mode[/\d+/].to_i]
    end

    # groups: the same EvalGroup array groups() already produced — reused
    # rather than re-parsing evals/results/*.jsonl a second time. Each
    # group already carries success_count/run_count, so this just resums
    # those across scenario+mode boundaries, grouped by model_label alone.
    def self.pass_fail_by_model(groups)
      groups.group_by(&:model_label).map do |model_label, model_groups|
        pass = model_groups.sum(&:success_count)
        total = model_groups.sum(&:run_count)
        ModelPassFail.new(model_label, pass, total - pass)
      end.sort_by(&:model_label)
    end

    # Same rows as pass_fail_by_model, ranked by win rate (ties broken by
    # more total runs first — more data behind the same rate is worth
    # ranking above it) instead of pass_fail_by_model's alphabetical
    # order. A separate method rather than changing that one's sort so the
    # /evals "pass vs. fail by model" chart's bar order stays untouched —
    # this one is specifically for /scoreboard, where ranking is the point.
    def self.leaderboard(groups)
      pass_fail_by_model(groups).sort_by { |r| [-r.win_rate, -r.total] }
    end

    def self.heatmaps(groups)
      groups.group_by(&:scenario).map do |scenario, scenario_groups|
        models = scenario_groups.map(&:model_label).uniq.sort
        modes = scenario_groups.map(&:mode).uniq.sort_by { |m| mode_sort_key(m) }
        cells = scenario_groups.each_with_object({}) { |g, h| h[[g.model_label, g.mode]] = g }
        HeatmapScenario.new(scenario, models, modes, cells)
      end.sort_by(&:scenario)
    end
  end
end
