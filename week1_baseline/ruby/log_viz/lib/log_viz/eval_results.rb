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
    def model_label = "#{backend}/#{model}"
    def success? = data["task_success"] == true
    # True when the agent wrote a non-empty output file whose content didn't
    # match the scenario's expected keywords — a real, observed failure mode
    # (a small model wrote a bar's menu to the bakery output path, having
    # admitted in its own summary it never found a bakery). Distinct from a
    # plain FAIL (no file at all) since it means the agent substituted
    # plausible-looking content instead of admitting it couldn't finish.
    def fabricated? = data["output_written"] == true && data["content_matched"] == false
    # False when mud_connect() never once reported success in the session
    # log (checked from the MUD server's own response text, not anything
    # the model claimed) — nil (not data-absent, genuinely unknown) for
    # results written before this check existed. Caught a real incident:
    # a model whose every mud_connect() attempt timed out still invented a
    # complete fake bakery menu from scratch and reported the task done.
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

  module EvalResults
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
