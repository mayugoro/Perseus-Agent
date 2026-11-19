#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { stdin } from "node:process";

function readStdin(): Promise<string> {
  return new Promise((res) => {
    let b = "";
    stdin.setEncoding("utf8");
    stdin.on("data", (c) => (b += c));
    stdin.on("end", () => res(b));
  });
}

function run(cmd: string, args: string[], input?: string): boolean {
  const r = spawnSync(cmd, args, { input, stdio: ["pipe", "inherit", "ignore"] });
  return r.status === 0;
}

function has(cmd: string): boolean {
  return spawnSync("sh", ["-c", `command -v ${cmd}`], { stdio: "ignore" }).status === 0;
}

function highlight(code: string, lang = ""): string {
  const C = { kw: "\x1b[35m", str: "\x1b[32m", num: "\x1b[33m", com: "\x1b[2m", rst: "\x1b[0m" };
  const kw = /\b(def|class|return|if|else|elif|for|while|import|from|try|except|finally|with|as|async|await|function|const|let|var|new|throw|catch|switch|case|break|continue|public|private|static|void|int|string|bool|true|false|null|None|True|False|package|fun|val)\b/g;
  return code.split("\n").map((line) => {
    const t = line.trimStart();
    if (t.startsWith("#") || t.startsWith("//")) return C.com + line + C.rst;
    return line
      .replace(/(["'`])(?:\\.|(?!\1).)*\1/g, (m) => C.str + m + C.rst)
      .replace(kw, (m) => C.kw + m + C.rst)
      .replace(/\b\d+(\.\d+)?\b/g, (m) => C.num + m + C.rst);
  }).join("\n");
}

async function main() {
  const [cmd, ...args] = process.argv.slice(2);
  if (cmd === "copy") {
    const text = await readStdin();
    for (const [c, a] of [["termux-clipboard-set", []], ["wl-copy", []], ["xclip", ["-selection", "clipboard"]], ["pbcopy", []]] as [string, string[]][]) {
      if (has(c) && run(c, a, text)) return;
    }
    console.error("no clipboard tool found");
    process.exit(1);
  }
  if (cmd === "notify") {
    const title = args[0] || "Perseus";
    const body = args[1] || "Task finished";
    if (has("termux-notification")) { run("termux-notification", ["--title", title, "--content", body]); return; }
    if (has("notify-send")) { run("notify-send", [title, body]); return; }
    console.error("no notification tool found");
    process.exit(1);
  }
  if (cmd === "open") {
    const url = args[0] || "";
    if (has("termux-open-url")) return void run("termux-open-url", [url]);
    if (has("xdg-open")) return void run("xdg-open", [url]);
    console.error("no opener found");
    process.exit(1);
  }
  if (cmd === "size") {
    console.log(JSON.stringify({ cols: process.stdout.columns || 80, rows: process.stdout.rows || 24, color: process.stdout.hasColors ? process.stdout.hasColors() : false }));
    return;
  }
  if (cmd === "highlight") {
    const code = await readStdin();
    process.stdout.write(highlight(code, args[0] || ""));
    return;
  }
  console.error("usage: perseus-ui <copy|notify|open|size|highlight>");
  process.exit(2);
}
main();
