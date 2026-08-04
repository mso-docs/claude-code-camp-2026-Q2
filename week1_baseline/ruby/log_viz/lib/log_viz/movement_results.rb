require "time"
require_relative "session"

module LogViz
  # Per-eval-run movement metrics, joined to EvalRun's model/scenario/batch
  # metadata — the aggregation layer behind the movement scoreboard, the
  # trend-over-time chart, and the synchronized replay's run picker. A full
  # Session.load + movement_trace costs ~2.5ms/run (measured against the
  # ~400-row bakery.jsonl); cheap once, but re-paying that for every run on
  # every request is exactly what /evals's own index route already avoids
  # doing (see app.rb's `get "/"` comment on why it doesn't Session.load
  # per row) — so this memoizes by absolute log path. Safe to cache for the
  # life of the process: a finished trial's session.jsonl never changes
  # after evals/score.py writes it.
  module MovementResults
    Row = Struct.new(:run, :trace, :blocked_count, :room_count, :dwell_s,
                      :duration_s, :date, keyword_init: true) do
      def model_label = run.model_label
      def scenario = run.scenario
      def mode = run.mode
      def success? = run.success?
      def room_names = trace.map(&:room)
    end

    @cache = {}

    # OpenCode/OpenRouter runs (score_opencode.py) have no per-step
    # transcript at all, so their Session parses to zero move/look
    # entries — MovementResults silently omits them (nil row) rather than
    # rendering a misleading all-zero bar for a harness that was never
    # instrumented for this. See the movement view's own note about this.
    def self.for_runs(runs, results_dir)
      runs.filter_map { |run| row_for(run, results_dir) }
    end

    def self.row_for(run, results_dir)
      path = resolve_path(run.log_path, results_dir)
      return nil unless path

      cached = (@cache[path] ||= build_row(path))
      return nil unless cached

      # The underlying session/trace is cached by path; the EvalRun struct
      # itself is cheap and always fresh from the caller, since the same
      # log path is in principle addressable from more than one route.
      row = cached.dup
      row.run = run
      row
    end

    def self.build_row(path)
      session = Session.load(path)
      trace = session.movement_trace
      return nil if trace.empty?

      Row.new(trace: trace,
              blocked_count: session.total_blocked_count,
              room_count: trace.map(&:room).uniq.length,
              dwell_s: trace.sum { |s| s.duration_s.to_f },
              duration_s: nil,
              date: parse_date(session.started_at))
    rescue StandardError
      nil
    end

    def self.parse_date(iso)
      return nil if iso.to_s.empty?

      Time.parse(iso)
    rescue ArgumentError
      nil
    end

    ModelSummary = Struct.new(:model_label, :run_count, :avg_blocked, :avg_rooms,
                              :avg_dwell_s, :success_rate, keyword_init: true)

    # One row per model, alphabetical — same split as EvalResults'
    # pass_fail_by_model (stable order for a table/legend) vs. leaderboard
    # (ranked for "who's winning"); callers needing rank order re-sort by
    # avg_blocked themselves rather than this method changing shape.
    def self.by_model(rows)
      rows.group_by(&:model_label).map do |label, rs|
        n = rs.length
        ModelSummary.new(
          model_label: label, run_count: n,
          avg_blocked: rs.sum(&:blocked_count).to_f / n,
          avg_rooms: rs.sum(&:room_count).to_f / n,
          avg_dwell_s: rs.sum(&:dwell_s).to_f / n,
          success_rate: rs.count(&:success?).to_f / n * 100
        )
      end.sort_by(&:model_label)
    end

    BatchPoint = Struct.new(:batch_id, :date, :avg_blocked, :avg_rooms, :run_count, keyword_init: true)

    # {model_label => [BatchPoint, ...]} in chronological order — the trend
    # chart's series. A model only gets a point for batches it actually ran
    # in (batches interleave models rather than every model appearing in
    # every batch), so series lengths differ; that's a real gap, not
    # padded with zeros.
    def self.trend_by_model(rows)
      rows.group_by(&:model_label).transform_values do |rs|
        rs.group_by { |r| r.run.batch_id }.filter_map do |batch_id, brs|
          date = brs.map(&:date).compact.min
          next unless date

          n = brs.length
          BatchPoint.new(batch_id: batch_id, date: date,
                         avg_blocked: brs.sum(&:blocked_count).to_f / n,
                         avg_rooms: brs.sum(&:room_count).to_f / n, run_count: n)
        end.sort_by(&:date)
      end
    end

    # [[scenario, mode], run_count] pairs, most-populous first — feeds the
    # replay picker's default (see app.rb's /movement/replay route).
    def self.scenario_modes(rows)
      rows.group_by { |r| [r.scenario, r.mode] }
          .map { |key, rs| [key, rs.length] }
          .sort_by { |_, n| -n }
    end

    # The most recent run per model within one scenario+mode — replay's
    # default cast, one dot per model on the shared map. "Most recent" by
    # session start time, not batch_id string order (same underlying
    # timestamp, but this reuses the date this module already parsed
    # rather than re-deriving it from the id string a second time).
    def self.latest_by_model(rows, scenario:, mode:)
      rows.select { |r| r.scenario == scenario && r.mode == mode }
          .group_by(&:model_label)
          .filter_map { |label, rs| [label, rs.max_by { |r| r.date || Time.at(0) }] }
          .to_h
    end

    # Same escape-prevention as app.rb's eval_run_log_path — this module
    # has no Sinatra `settings` to reuse that helper directly, and results
    # get here via each run's own log_path field, not a URL splat, but the
    # containment check is worth keeping regardless of the source.
    def self.resolve_path(rel, results_dir)
      base = File.expand_path(results_dir)
      candidate = File.expand_path(File.join(base, rel.to_s))
      return nil unless candidate.start_with?("#{base}#{File::SEPARATOR}")
      return nil unless File.file?(candidate)

      candidate
    end
  end
end
