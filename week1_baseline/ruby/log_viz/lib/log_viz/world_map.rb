require "json"
require "set"

module LogViz
  # CircleMUD's real room graph (vnum -> name, exits), exported once from
  # the world's .wld files by week0_explore/circlemud-world-parser's
  # export_room_graph.py into data/circlemud_rooms.json — see that script
  # for why this is a static asset rather than shelling out to Python per
  # request. Session logs only ever give us a room *name* (parsed from the
  # MUD's ANSI text), never a vnum, so this exists to answer "which room did
  # they actually mean" — needed to place different sessions' paths on one
  # shared, spatially consistent map instead of each session getting its
  # own unrelated layout (see Session#movement_trace / app.rb's
  # movement_layout, which still do that for the single-session view).
  class WorldMap
    def self.instance
      @instance ||= new(File.expand_path("../../data/circlemud_rooms.json", __dir__))
    end

    def initialize(path)
      raw = JSON.parse(File.read(path))
      @rooms = raw.each_with_object({}) do |(vnum, r), h|
        h[vnum.to_i] = { name: r["name"], exits: r["exits"].transform_values(&:to_i).values }
      end
      @vnums_by_name = Hash.new { |h, k| h[k] = [] }
      @rooms.each { |vnum, r| @vnums_by_name[normalize(r[:name])] << vnum }
    end

    def name_for(vnum) = @rooms[vnum]&.fetch(:name, nil)

    Traffic = Struct.new(:vnum, :dwell_s, :visits, :run_count, keyword_init: true)

    # Aggregate traffic per room across an arbitrary set of MovementResults
    # rows — the whole-world heatmap's data (see app.rb's /movement/world),
    # as opposed to resolve_trace's single-session use. `run_count` counts
    # distinct runs that touched a room at all, separate from `visits`
    # (one run can visit the same room several times), since "how many
    # different attempts passed through here" and "how much total time got
    # spent here" tell different stories — one stuck run inflates dwell_s
    # without meaning the room saw much real traffic.
    #
    # Returns [traffic_array, resolved_segment_count, total_segment_count]
    # — the last two are for the view's honesty caveat about how much of
    # the aggregate actually landed on the map (resolve_trace can't place
    # every room name; see its own comment for why).
    def room_traffic(rows)
      stats = Hash.new { |h, k| h[k] = { dwell_s: 0.0, visits: 0, runs: Set.new } }
      resolved = 0
      total = 0

      rows.each do |row|
        vnums = resolve_trace(row.room_names)
        row.trace.zip(vnums).each do |seg, vnum|
          total += 1
          next unless vnum

          resolved += 1
          s = stats[vnum]
          s[:dwell_s] += seg.duration_s.to_f
          s[:visits] += 1
          s[:runs] << (row.run.log_path || row.object_id)
        end
      end

      traffic = stats.map do |vnum, s|
        Traffic.new(vnum: vnum, dwell_s: s[:dwell_s], visits: s[:visits], run_count: s[:runs].size)
      end

      [traffic, resolved, total]
    end

    def adjacent?(a, b)
      return false unless a && b

      @rooms[a]&.fetch(:exits, [])&.include?(b) || @rooms[b]&.fetch(:exits, [])&.include?(a)
    end

    # True .wld exits between two members of `vnums` — the edge set a
    # shared-map layout should use (see app.rb's movement_layout), since it
    # reflects the dungeon's real structure rather than just whichever
    # links one session happened to walk.
    def structural_edges(vnums)
      set = vnums.to_set
      vnums.flat_map { |v| (@rooms[v]&.fetch(:exits, []) || []).select { |n| set.include?(n) }.map { |n| [v, n] } }
           .map(&:sort).uniq
    end

    # Resolves an ordered, duplicates-allowed sequence of room *names* (one
    # per visited segment, in the order a session walked them) to vnums.
    # Most CircleMUD room names are unique across all ~12.7k rooms and
    # resolve immediately; the ones that aren't (~1.5k names are reused
    # across zones — "The Dark Passageway", "The Sewers", etc.) are
    # disambiguated by adjacency: if the room visited immediately before or
    # after already resolved, only the candidate vnum that's actually
    # linked to that neighbor in the real world graph can be correct. Runs
    # a few passes since resolving one ambiguous room can be exactly what
    # unblocks its other ambiguous neighbor. Entries that stay nil either
    # don't exist under that name in the world files at all (e.g. a
    # different, unmapped area) or never got an adjacent anchor to
    # disambiguate against.
    def resolve_trace(room_names)
      resolved = Array.new(room_names.length)

      room_names.each_with_index do |name, i|
        candidates = @vnums_by_name[normalize(name)]
        resolved[i] = candidates.first if candidates.length == 1
      end

      4.times do
        progressed = false

        room_names.each_with_index do |name, i|
          next if resolved[i]

          candidates = @vnums_by_name[normalize(name)]
          next if candidates.empty?

          neighbors = [(resolved[i - 1] if i.positive?), resolved[i + 1]].compact
          next if neighbors.empty?

          # Intersection, not union: with two known neighbors (the segment
          # right before and right after), the real room is one MUD move
          # from *both* of them, so a candidate adjacent to only one is
          # ruled out, not accepted — this is what disambiguates a room
          # flanked by two same-named neighbors (e.g. Market Square sitting
          # between two different "Main Street" segments), which a
          # match-any check can never narrow past.
          matches = neighbors.map { |n| candidates.select { |c| adjacent?(c, n) } }.reduce(:&)
          if matches.length == 1
            resolved[i] = matches.first
            progressed = true
          end
        end

        break unless progressed
      end

      resolved
    end

    private

    def normalize(name) = name.to_s.strip.downcase
  end
end
