/**
 * HAKU — Heritage Command User Interface (CommonJS)
 */

const fs = require("fs");
const path = require("path");
const readline = require("readline");
require("dotenv").config();
const OpenAI = require("openai");
const { createAgent, listAgents, AGENTS_DIR } = require("./agent-factory");

// ─────────────────────────────────────────────
// Config + Core Prompt
// ─────────────────────────────────────────────

const configPath = path.join(__dirname, "haku-config.json");
if (!fs.existsSync(configPath)) {
  console.error("❌ Missing haku-config.json");
  process.exit(1);
}
const CONFIG = JSON.parse(fs.readFileSync(configPath, "utf8"));

const corePromptPath = path.join(__dirname, "heritage-core-prompt.txt");
if (!fs.existsSync(corePromptPath)) {
  console.error("❌ Missing heritage-core-prompt.txt");
  process.exit(1);
}
const CORE_PROMPT = fs.readFileSync(corePromptPath, "utf8");

// ─────────────────────────────────────────────
// OpenAI Client
// ─────────────────────────────────────────────

if (!process.env.OPENAI_API_KEY) {
  console.error("❌ Missing OPENAI_API_KEY in .env");
  process.exit(1);
}

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY
});

// ─────────────────────────────────────────────
// Ask Model Utility
// ─────────────────────────────────────────────

async function askModel({ system, user, model }) {
  const completion = await openai.chat.completions.create({
    model,
    messages: [
      { role: "system", content: system },
      { role: "user", content: user }
    ],
    temperature: 0.2
  });

  return completion.choices[0].message.content.trim();
}

// ─────────────────────────────────────────────
// Routing Functions
// ─────────────────────────────────────────────

async function routeToExec(q) {
  return askModel({
    system: CORE_PROMPT + "\n\n[ACTIVE GROUP: H-EXEC]",
    user: q,
    model: CONFIG.models.exec
  });
}

async function routeToCouncil(q) {
  return askModel({
    system: CORE_PROMPT + "\n\n[ACTIVE GROUP: H-COUNCIL]",
    user: q,
    model: CONFIG.models.council
  });
}

async function routeToAll(q) {
  const exec = await routeToExec(q);
  const council = await routeToCouncil(q);

  return askModel({
    system:
      CORE_PROMPT +
      "\n\nMerge EXEC and COUNCIL into: Exec View, Council View, Integrated Summary.",
    user: `EXEC VIEW:\n${exec}\n\nCOUNCIL VIEW:\n${council}`,
    model: CONFIG.models.merge
  });
}

// ─────────────────────────────────────────────
// Agent Factory Commands
// ─────────────────────────────────────────────

function parseArgs(str) {
  // naive: split by space, first token is command, rest is args
  return str.trim().split(/\s+/);
}

async function handleNewAgent(cmd) {
  // Examples:
  //   new-agent advisor "Exec Alpha"
  //   new-agent advisor "Council Scout" H-COUNCIL
  //   new-agent workstream "Shopper Ops" WS-SHOPPER

  const parts = cmd.replace(/^new-agent\s+/, "").trim();
  if (!parts) {
    console.log(
      "Usage:\n  new-agent advisor \"Name\" [GROUP_ID]\n  new-agent workstream \"Name\" [WORKSTREAM_ID]"
    );
    return;
  }

  // very simple parser: type, then name in quotes, then optional id
  const match = parts.match(/^(advisor|workstream)\s+"([^"]+)"\s*([A-Z0-9\-_]*)/i);
  if (!match) {
    console.log(
      "Parse error. Example:\n  new-agent advisor \"Exec Alpha\" H-EXEC\n  new-agent workstream \"Shopper Ops\" WS-SHOPPER"
    );
    return;
  }

  const type = match[1].toLowerCase();
  const name = match[2];
  const idOrWs = match[3] || "";

  const options = {};
  if (type === "advisor" && idOrWs) {
    options.groupId = idOrWs;
  }
  if (type === "workstream" && idOrWs) {
    options.workstreamId = idOrWs;
  }

  const { filePath, agent } = createAgent(type, name, options);

  console.log("✅ Agent created:");
  console.log("  File:", filePath);
  console.log("  ID:", agent.meta.id);
  console.log("  Name:", agent.name);
}

function handleListAgents() {
  const files = listAgents();
  if (!files.length) {
    console.log("No agents defined yet. Use `new-agent ...` to create one.");
    return;
  }

  console.log(`Agents in ${AGENTS_DIR}:`);
  files.forEach((f) => {
    console.log(" - " + f);
  });
}

// ─────────────────────────────────────────────
// Command Handler
// ─────────────────────────────────────────────

async function handleCommand(line) {
  const cmd = line.trim();
  if (!cmd) return;

  if (cmd === "help") {
    console.log(`
Commands:
  exec <question>         Ask Heritage Executive Branch
  council <question>      Ask Heritage Council of Advisors
  all <question>          Ask both + merged summary

  new-agent advisor "Name" [GROUP_ID]
  new-agent workstream "Name" [WORKSTREAM_ID]
                          Create an agent JSON in ./agents

  list-agents             List all agent JSON files

  exit                    Quit Haku
`);
    return;
  }

  if (cmd.startsWith("exec ")) {
    const q = cmd.slice(5);
    const r = await routeToExec(q);
    console.log("\n[EXEC RESPONSE]\n" + r + "\n");
    return;
  }

  if (cmd.startsWith("council ")) {
    const q = cmd.slice(8);
    const r = await routeToCouncil(q);
    console.log("\n[COUNCIL RESPONSE]\n" + r + "\n");
    return;
  }

  if (cmd.startsWith("all ")) {
    const q = cmd.slice(4);
    const r = await routeToAll(q);
    console.log("\n[ALL ADVISORS]\n" + r + "\n");
    return;
  }

  if (cmd.startsWith("new-agent ")) {
    await handleNewAgent(cmd);
    return;
  }

  if (cmd === "list-agents") {
    handleListAgents();
    return;
  }

  if (cmd === "exit") {
    console.log("Exiting Haku.");
    process.exit(0);
  }

  console.log("Unknown command. Type 'help'.");
}

// ─────────────────────────────────────────────
// CLI Boot
// ─────────────────────────────────────────────

console.log("🔥 Haku console ready. Type 'help'.");

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout
});

rl.setPrompt("Haku> ");
rl.prompt();

rl.on("line", async (line) => {
  try {
    await handleCommand(line);
  } catch (err) {
    console.error("❌ Error:", err.message || err);
  }
  rl.prompt();
});
