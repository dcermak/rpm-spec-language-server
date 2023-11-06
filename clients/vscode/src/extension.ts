import * as net from "net";

import { LanguageClient, ServerOptions } from "vscode-languageclient/node";

function startLangServerTCP(addr: number): LanguageClient {
  let clientSocket: net.Socket;

  const serverOptions: ServerOptions = () => {
    return new Promise((resolve) => {
      clientSocket = new net.Socket();

      clientSocket.connect(addr, "127.0.0.1", () => {
        resolve({
          reader: clientSocket,
          writer: clientSocket,
        });
      });

      clientSocket.on("close", () => {
        setTimeout(() => {
          clientSocket.connect(addr, "127.0.0.1");
        }, 1000);
      });
    });
  };

  return new LanguageClient(`tcp lang server (port ${addr})`, serverOptions, {
    documentSelector: [{ scheme: "file", language: "rpmspec" }],
    outputChannelName: "[rpmspec_lsp] RPMSpecFileLanguageServer",
  });
}

let client: LanguageClient;

export async function activate() {
  client = startLangServerTCP(2087);
  await client.start();
}

export function deactivate(): Thenable<void> {
  return client ? client.stop() : Promise.resolve();
}
