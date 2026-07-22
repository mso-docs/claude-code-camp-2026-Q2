#!/usr/bin/env node

import { access } from "node:fs/promises"
import path from "node:path"
import process from "node:process"
import { createOpencode } from "@opencode-ai/sdk"

const directory = process.cwd()
const prompt = process.argv.slice(2).join(" ").trim() || "start"

await Promise.all([
  access(path.join(directory, ".opencode/agents/play-mud.md")),
  access(path.join(directory, ".ollama/.agents/play-mud.md")),
  access(path.join(directory, "QUEST.md")),
]).catch(() => {
  throw new Error("Run this SDK from week0_explore/explore_architecture/03_subagent_sdk")
})

const opencode = await createOpencode({ port: 0, timeout: 15_000 })
try {
  if (prompt === "--check") {
    const [agentsResult, toolsResult] = await Promise.all([
      opencode.client.app.agents({ query: { directory }, throwOnError: true }),
      opencode.client.tool.ids({ query: { directory }, throwOnError: true }),
    ])
    const agents = agentsResult.data ?? []
    const tools = toolsResult.data ?? []
    if (!agents.some((agent) => agent.name === "play-mud")) throw new Error("play-mud agent is not registered")
    const expected = ["mud_capture", "mud_checkpoint", "mud_doctor", "mud_memory", "mud_send", "mud_start", "mud_status"]
    const missing = expected.filter((id) => !tools.includes(id))
    if (missing.length) throw new Error(`Missing OpenCode tools: ${missing.join(", ")}`)
    console.log("OpenCode SDK, play-mud agent, and all MUD tools are ready.")
  } else {
    const created = await opencode.client.session.create({
      query: { directory },
      body: { title: `MUD player: ${prompt}` },
      throwOnError: true,
    })
    const session = created.data
    if (!session) throw new Error("OpenCode did not return a session")

    console.error(`OpenCode MUD session: ${session.id}`)
    const response = await opencode.client.session.prompt({
      path: { id: session.id },
      query: { directory },
      body: {
        agent: "play-mud",
        parts: [{ type: "text", text: prompt }],
      },
      throwOnError: true,
    })

    const parts = response.data?.parts ?? []
    const text = parts.filter((part) => part.type === "text").map((part) => part.text).join("\n")
    if (text) process.stdout.write(`${text}\n`)
  }
} finally {
  opencode.server.close()
}
