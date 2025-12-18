/**
 * agent-factory.js
 * Simple agent "assembly line" for Haku (CommonJS).
 */

const fs = require("fs");
const path = require("path");

const AGENTS_DIR = path.join(__dirname, "agents");

// Ensure agents directory exists
if (!fs.existsSync(AGENTS_DIR)) {
  fs.mkdirSync(AGENTS_DIR, { recursive: true });
}

function sanitizeName(name) {
  return name.toLowerCase().replace(/[^a-z0-9-_]+/g, "-");
}

function timestamp() {
  return new Date().toISOString();
}

/**
 * Create a new agent definition JSON on disk.
 * type: "advisor" | "workstream"
 * name: display name
 * options: { groupId?, workstreamId?, notes? }
 */
function createAgent(type, name, options = {}) {
  const idBase = sanitizeName(name || "agent");
  const fileName = `${type}-${idBase}-${Date.now()}.json`;
  const filePath = path.join(AGENTS_DIR, fileName);

  const agent = {
    meta: {
      id: `${type.toUpperCase()}-${idBase}`,
      type,
      created_at: timestamp()
    },
    name,
    groupId: options.groupId || null,
    workstreamId: options.workstreamId || null,
    role: options.role || null,
    notes: options.notes || [],
    routing: {
      default_target:
        type === "advisor" ? (options.groupId || "H-EXEC") : options.workstreamId,
      allowed_targets: options.allowed_targets || []
    },
    prompt: {
      system: options.systemPrompt || "",
      style: {
        tone: "heritage-rugged",
        brevity: "concise",
        constraints: [
          "No hype",
          "Conservative projections until data proves otherwise",
          "Respect Minimalist → Maximum Valuation rule"
        ]
      }
    }
  };

  fs.writeFileSync(filePath, JSON.stringify(agent, null, 2), "utf8");

  return {
    filePath,
    agent
  };
}

function listAgents() {
  if (!fs.existsSync(AGENTS_DIR)) return [];
  return fs
    .readdirSync(AGENTS_DIR)
    .filter((f) => f.endsWith(".json"))
    .map((f) => path.join(AGENTS_DIR, f));
}

module.exports = {
  createAgent,
  listAgents,
  AGENTS_DIR
};
