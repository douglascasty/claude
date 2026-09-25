import { createInterface } from "node:readline";
import { Writable } from "node:stream";

/**
 * Reads a password without echoing it. When stdin is not a TTY (e.g. piped
 * from a secret manager), the first line of stdin is used instead.
 */
export async function promptPassword(label = "Password: "): Promise<string> {
  const interactive = Boolean(process.stdin.isTTY);
  let muted = false;
  const output = new Writable({
    write(chunk, _encoding, callback) {
      if (!muted) process.stderr.write(chunk);
      callback();
    },
  });
  const rl = createInterface({ input: process.stdin, output, terminal: interactive });
  try {
    return await new Promise<string>((resolve, reject) => {
      rl.once("close", () => reject(new Error("no password provided")));
      rl.question(label, (answer) => {
        if (interactive) process.stderr.write("\n");
        resolve(answer);
      });
      muted = interactive;
    });
  } finally {
    rl.removeAllListeners("close");
    rl.close();
  }
}
