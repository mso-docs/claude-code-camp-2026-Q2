import { tool } from "@opencode-ai/plugin"
import { execFile } from "node:child_process"
import { appendFile, readFile, writeFile } from "node:fs/promises"
import path from "node:path"
import { promisify } from "node:util"

const execFileAsync = promisify(execFile)
let commandsSinceCheckpoint = 0

function projectPath(directory: string, relative: string) {
  return path.join(directory, relative)
}

async function requireProject(directory: string) {
  try {
    await readFile(projectPath(directory, "QUEST.md"), "utf8")
    await readFile(projectPath(directory, ".ollama/.agents/play-mud.md"), "utf8")
  } catch {
    throw new Error("Launch OpenCode from week0_explore/explore_architecture/03_subagent_sdk")
  }
}

async function runMud(directory: string, action: string, command?: string) {
  await requireProject(directory)
  const executable = projectPath(directory, ".ollama/.agents/tools/mud.sh")
  const args = command === undefined ? [action] : [action, command]
  try {
    const { stdout, stderr } = await execFileAsync(executable, args, {
      cwd: directory,
      maxBuffer: 1024 * 1024,
      timeout: action === "start" ? 120_000 : 30_000,
    })
    return [stdout, stderr].filter(Boolean).join("\n").trim()
  } catch (error) {
    const failure = error as Error & { stdout?: string; stderr?: string }
    throw new Error([failure.message, failure.stdout, failure.stderr].filter(Boolean).join("\n"))
  }
}

export const doctor = tool({
  description: "Check the supplied CircleMUD tools and hidden login configuration. Always call before mud_start.",
  args: {},
  async execute(_args, context) {
    return runMud(context.directory, "doctor")
  },
})

export const start = tool({
  description: "Ensure CircleMUD is ready and create or reuse exactly one authenticated session. This is the only login path.",
  args: {},
  async execute(_args, context) {
    commandsSinceCheckpoint = 0
    return runMud(context.directory, "start")
  },
})

export const status = tool({
  description: "Inspect server and authenticated-session status without changing game state.",
  args: {},
  async execute(_args, context) {
    return runMud(context.directory, "status")
  },
})

export const capture = tool({
  description: "Read recent redacted MUD output without sending a gameplay command.",
  args: {},
  async execute(_args, context) {
    return runMud(context.directory, "capture")
  },
})

export const send = tool({
  description: "Send exactly one command through the authenticated MUD socket. After four commands, call mud_checkpoint before continuing.",
  args: {
    command: tool.schema.string().min(1).describe("One MUD command, without a newline"),
  },
  async execute(args, context) {
    if (commandsSinceCheckpoint >= 4) {
      throw new Error("Checkpoint required: call mud_checkpoint with current verified state before another MUD command.")
    }
    const output = await runMud(context.directory, "send", args.command)
    commandsSinceCheckpoint += 1
    return `${output}\n\nSDK_COMMAND_COUNT=${commandsSinceCheckpoint}/4`
  },
})

export const memory = tool({
  description: "Load the active quest and all durable MUD memory in one call. Use at the beginning of every run and after compaction.",
  args: {},
  async execute(_args, context) {
    await requireProject(context.directory)
    const files = ["QUEST.md", "data/session.md", "data/checkpoints.md", "data/player.md", "data/world.md", "data/commands.md"]
    const sections = await Promise.all(files.map(async (file) => {
      const content = await readFile(projectPath(context.directory, file), "utf8")
      return `===== ${file} =====\n${content.trim()}`
    }))
    return sections.join("\n\n")
  },
})

export const checkpoint = tool({
  description: "Persist a resumable MUD handoff and reset the four-command gate. Call immediately after discoveries, state changes, combat, or milestones.",
  args: {
    status: tool.schema.enum(["in_progress", "blocked", "complete"]),
    room: tool.schema.string().min(1).describe("Last room confirmed by captured live output"),
    summary: tool.schema.string().min(1).describe("What live output confirmed since the last checkpoint"),
    playerChanges: tool.schema.string().min(1).describe("Verified player state changes, or 'none'"),
    worldChanges: tool.schema.string().min(1).describe("Verified world discoveries, or 'none'"),
    nextAction: tool.schema.string().min(1).describe("Exact safest next gameplay action"),
  },
  async execute(args, context) {
    await requireProject(context.directory)
    const timestamp = new Date().toISOString()
    const session = `# MUD Session Handoff\n\n- Updated: ${timestamp}\n- Objective status: ${args.status}\n- Last verified room: ${args.room}\n- Commands since checkpoint: 0\n- Last result: ${args.summary}\n- Player changes: ${args.playerChanges}\n- World changes: ${args.worldChanges}\n- Next action: ${args.nextAction}\n`
    const checkpoint = `\n## ${timestamp}\n\n- Status: ${args.status}\n- Room: ${args.room}\n- Result: ${args.summary}\n- Player changes: ${args.playerChanges}\n- World changes: ${args.worldChanges}\n- Next action: ${args.nextAction}\n`
    await writeFile(projectPath(context.directory, "data/session.md"), session, "utf8")
    await appendFile(projectPath(context.directory, "data/checkpoints.md"), checkpoint, "utf8")
    commandsSinceCheckpoint = 0
    return "Checkpoint persisted to data/session.md and data/checkpoints.md. Merge verified facts into data/player.md and data/world.md before continuing."
  },
})
