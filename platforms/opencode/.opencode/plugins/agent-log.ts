import type { Plugin } from "@opencode-ai/plugin"
import { fileURLToPath } from "node:url"

const script = fileURLToPath(new URL("../scripts/log_agent.py", import.meta.url))

export const AgentLog: Plugin = async ({ client, $, directory }) => {
  const write = async (row: Record<string, unknown>) => {
    const body = new Response(JSON.stringify({ cwd: directory, ...row }))
    const r = await $`python3 ${script} < ${body}`.quiet().nothrow()
    if (r.exitCode !== 0) {
      await client.app.log({ body: { service: "agent-log", level: "warn", message: r.stderr.toString() } })
    }
  }

  return {
    "tool.execute.before": async (input, output) => {
      if (input.tool !== "task") return
      await write({
        session_id: input.sessionID,
        agent: output.args?.subagent_type,
        description: "start",
        prompt: output.args?.prompt,
        response: null,
        tool_use_id: input.callID,
      })
    },
    "tool.execute.after": async (input, output) => {
      if (input.tool !== "task") return
      await write({
        session_id: input.sessionID,
        agent: input.args?.subagent_type,
        description: input.args?.description,
        prompt: input.args?.prompt,
        response: output.output,
        tool_use_id: input.callID,
      })
    },
    event: async ({ event }) => {
      if (event.type !== "session.idle") return
      const id = event.properties.sessionID
      const session = await client.session.get({ path: { id } })
      if (!session.data || session.data.parentID) return
      const messages = await client.session.messages({ path: { id } })
      const last = (messages.data ?? []).filter((m) => m.info.role === "assistant").at(-1)
      const text = last?.parts.flatMap((p) => (p.type === "text" ? [p.text] : [])).join("\n")
      if (!text) return
      await write({ session_id: id, agent: "leader", description: "idle", prompt: null, response: text })
    },
  }
}
