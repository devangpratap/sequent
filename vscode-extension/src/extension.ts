import * as vscode from "vscode";
import { execFile, ChildProcess } from "child_process";
import * as path from "path";
import * as os from "os";
import * as fs from "fs";

// ---------------------------------------------------------------------------
// Types matching Sequent CLI --json output (list of summary dicts)
// ---------------------------------------------------------------------------

interface GnnResult {
  buggy: boolean;
  confidence: number;
  bug_lines: number[];
  inference_ms: number;
  attention?: Array<{ src: number; dst: number; weight: number }>;
}

interface Z3Result {
  result: string;
  checks: number;
  bugs_found: number;
  time_ms: number;
}

interface RepairResult {
  applied: boolean;
  description: string;
  verified: boolean;
  remaining_issues?: number;
}

interface FunctionResult {
  function: string;
  is_buggy: boolean;
  description: string;
  total_time_ms: number;
  gnn?: GnnResult;
  z3?: Z3Result;
  repair?: RepairResult;
}

// Types matching --cert output (richer, has counterexamples + repaired_code)

interface CertCounterexample {
  property: string;
  description: string;
  line: number | null;
  counterexample: Record<string, unknown>;
}

interface CertZ3 {
  result: string;
  properties_checked: number;
  properties_verified: number;
  counterexamples: CertCounterexample[];
}

interface CertRepair {
  description: string;
  verified: boolean;
  repaired_code: string | null;
}

interface CertFunction {
  name: string;
  verdict: "buggy" | "verified";
  consensus: string;
  time_ms: number;
  gnn?: {
    prediction: string;
    confidence: number;
    suspect_lines: number[];
  };
  z3?: CertZ3;
  repair?: CertRepair;
}

interface Certificate {
  sequent_version: string;
  timestamp: string;
  source_file: string;
  summary: {
    total_functions: number;
    verified: number;
    bugs_found: number;
  };
  functions: CertFunction[];
}

// ---------------------------------------------------------------------------
// Globals
// ---------------------------------------------------------------------------

let diagnosticCollection: vscode.DiagnosticCollection;
let statusBarItem: vscode.StatusBarItem;
let outputChannel: vscode.OutputChannel;

/** Debounce timer for on-save verification. */
let saveTimer: ReturnType<typeof setTimeout> | undefined;

/** Active child process, so we can cancel on re-trigger. */
let activeProcess: ChildProcess | undefined;

/** Cache of latest cert results per file URI, used by hover + code actions. */
const certCache = new Map<string, CertFunction[]>();

// ---------------------------------------------------------------------------
// Activation
// ---------------------------------------------------------------------------

export function activate(context: vscode.ExtensionContext): void {
  outputChannel = vscode.window.createOutputChannel("Sequent");

  // Diagnostics
  diagnosticCollection =
    vscode.languages.createDiagnosticCollection("sequent");
  context.subscriptions.push(diagnosticCollection);

  // Status bar
  statusBarItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Left,
    100
  );
  statusBarItem.command = "sequent.verifyFile";
  statusBarItem.text = "$(shield) Sequent";
  statusBarItem.tooltip = "Click to verify current file";
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);

  // Commands
  context.subscriptions.push(
    vscode.commands.registerCommand("sequent.verifyFile", () =>
      verifyFile(false)
    )
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("sequent.verifyFunction", () =>
      verifyFunction()
    )
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("sequent.autoRepair", (uri, funcName) =>
      applyRepair(uri as vscode.Uri, funcName as string)
    )
  );

  // On-save handler
  context.subscriptions.push(
    vscode.workspace.onDidSaveTextDocument((doc) => {
      const config = vscode.workspace.getConfiguration("sequent");
      if (!config.get<boolean>("autoVerify", true)) {
        return;
      }
      if (doc.languageId !== "python") {
        return;
      }
      // Debounce 500ms
      if (saveTimer) {
        clearTimeout(saveTimer);
      }
      saveTimer = setTimeout(() => {
        verifyFile(true);
      }, 500);
    })
  );

  // Clear diagnostics when a file is closed
  context.subscriptions.push(
    vscode.workspace.onDidCloseTextDocument((doc) => {
      diagnosticCollection.delete(doc.uri);
      certCache.delete(doc.uri.toString());
    })
  );

  // Hover provider
  context.subscriptions.push(
    vscode.languages.registerHoverProvider("python", {
      provideHover(document, position) {
        return provideSequentHover(document, position);
      },
    })
  );

  // Code action provider
  context.subscriptions.push(
    vscode.languages.registerCodeActionsProvider(
      "python",
      new SequentCodeActionProvider(),
      {
        providedCodeActionKinds:
          SequentCodeActionProvider.providedCodeActionKinds,
      }
    )
  );

  outputChannel.appendLine("Sequent extension activated.");
}

export function deactivate(): void {
  if (activeProcess) {
    activeProcess.kill();
    activeProcess = undefined;
  }
  if (saveTimer) {
    clearTimeout(saveTimer);
  }
}

// ---------------------------------------------------------------------------
// Core verification
// ---------------------------------------------------------------------------

function getSeverity(): vscode.DiagnosticSeverity {
  const config = vscode.workspace.getConfiguration("sequent");
  const level = config.get<string>("severity", "Error");
  switch (level) {
    case "Warning":
      return vscode.DiagnosticSeverity.Warning;
    case "Information":
      return vscode.DiagnosticSeverity.Information;
    case "Hint":
      return vscode.DiagnosticSeverity.Hint;
    default:
      return vscode.DiagnosticSeverity.Error;
  }
}

function getPythonPath(): string {
  const config = vscode.workspace.getConfiguration("sequent");
  return config.get<string>("pythonPath", "python3");
}

/**
 * Run `sequent check <file> --cert <tmpfile>` and parse results.
 * We use --cert because it provides counterexample details and repaired code,
 * unlike --json which only has summary counts.
 */
async function runSequentCheck(
  filePath: string,
  functionName?: string
): Promise<Certificate | null> {
  const pythonPath = getPythonPath();
  const certPath = path.join(
    os.tmpdir(),
    `sequent-cert-${Date.now()}.json`
  );

  const args = ["-m", "sequent", "check", filePath, "--cert", certPath];
  if (functionName) {
    args.push("-f", functionName);
  }

  return new Promise((resolve) => {
    // Kill any running process
    if (activeProcess) {
      activeProcess.kill();
      activeProcess = undefined;
    }

    const timeout = 30_000; // 30 seconds
    const proc = execFile(
      pythonPath,
      args,
      { timeout, maxBuffer: 1024 * 1024 },
      (error, _stdout, stderr) => {
        activeProcess = undefined;

        // Clean up: read cert file then delete it
        try {
          if (fs.existsSync(certPath)) {
            const raw = fs.readFileSync(certPath, "utf-8");
            fs.unlinkSync(certPath);
            const cert = JSON.parse(raw) as Certificate;
            resolve(cert);
            return;
          }
        } catch (parseErr) {
          outputChannel.appendLine(
            `Failed to parse cert JSON: ${String(parseErr)}`
          );
        }

        // If cert file was not created, try --json fallback
        if (error) {
          const msg = stderr || error.message;
          if (msg.includes("No module named")) {
            vscode.window
              .showInformationMessage(
                "Sequent is not installed. Install with: pip install sequent-verify",
                "Copy install command"
              )
              .then((choice) => {
                if (choice) {
                  vscode.env.clipboard.writeText("pip install sequent-verify");
                }
              });
          } else if (
            error.killed ||
            msg.includes("SIGTERM") ||
            msg.includes("timed out")
          ) {
            vscode.window.showWarningMessage(
              "Sequent verification timed out (>30s). Try verifying a single function."
            );
          } else {
            // Exit code 1 is normal (means bugs found) -- only log if unexpected
            if (error.code !== 1) {
              outputChannel.appendLine(`Sequent error: ${msg}`);
            }
          }
        }

        resolve(null);
      }
    );

    activeProcess = proc;
  });
}

/**
 * Verify the active editor's file.
 * @param silent If true, do not show info messages for success.
 */
async function verifyFile(silent: boolean): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== "python") {
    if (!silent) {
      vscode.window.showInformationMessage(
        "Sequent: Open a Python file to verify."
      );
    }
    return;
  }

  const filePath = editor.document.fileName;
  statusBarItem.text = "$(loading~spin) Sequent...";

  const cert = await runSequentCheck(filePath);

  if (!cert) {
    statusBarItem.text = "$(shield) Sequent";
    return;
  }

  applyDiagnostics(editor.document, cert);
}

/**
 * Verify only the function at the cursor position.
 */
async function verifyFunction(): Promise<void> {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== "python") {
    vscode.window.showInformationMessage(
      "Sequent: Open a Python file to verify."
    );
    return;
  }

  // Find function name at cursor by scanning backwards for "def "
  const cursorLine = editor.selection.active.line;
  let funcName: string | undefined;

  for (let i = cursorLine; i >= 0; i--) {
    const lineText = editor.document.lineAt(i).text;
    const match = lineText.match(/^\s*def\s+(\w+)\s*\(/);
    if (match) {
      funcName = match[1];
      break;
    }
  }

  if (!funcName) {
    vscode.window.showInformationMessage(
      "Sequent: No function found at cursor position."
    );
    return;
  }

  statusBarItem.text = `$(loading~spin) Sequent: ${funcName}...`;

  const cert = await runSequentCheck(editor.document.fileName, funcName);

  if (!cert) {
    statusBarItem.text = "$(shield) Sequent";
    return;
  }

  applyDiagnostics(editor.document, cert);
}

// ---------------------------------------------------------------------------
// Diagnostics
// ---------------------------------------------------------------------------

function applyDiagnostics(
  document: vscode.TextDocument,
  cert: Certificate
): void {
  const diagnostics: vscode.Diagnostic[] = [];
  const severity = getSeverity();
  let verifiedCount = 0;
  let bugCount = 0;

  // Cache for hover and code actions
  certCache.set(document.uri.toString(), cert.functions);

  for (const func of cert.functions) {
    if (func.verdict === "verified") {
      verifiedCount++;
      continue;
    }

    bugCount++;

    // Find the function definition line in the document
    const funcLine = findFunctionLine(document, func.name);
    if (funcLine < 0) {
      continue;
    }

    // Determine the best line for the diagnostic
    let diagLine = funcLine;
    if (func.z3?.counterexamples && func.z3.counterexamples.length > 0) {
      const firstCx = func.z3.counterexamples[0];
      if (firstCx.line !== null && firstCx.line > 0) {
        // The line from Z3 is 1-indexed relative to function start,
        // or absolute -- check if it's in range
        const candidateLine = firstCx.line - 1; // convert to 0-indexed
        if (
          candidateLine >= 0 &&
          candidateLine < document.lineCount
        ) {
          diagLine = candidateLine;
        }
      }
    } else if (func.gnn?.suspect_lines && func.gnn.suspect_lines.length > 0) {
      // GNN suspect lines are 1-indexed relative to function
      const suspectLine = func.gnn.suspect_lines[0] + funcLine - 1;
      if (suspectLine >= 0 && suspectLine < document.lineCount) {
        diagLine = suspectLine;
      }
    }

    // Build the diagnostic range (underline the whole line)
    const lineText = document.lineAt(diagLine).text;
    const range = new vscode.Range(
      diagLine,
      lineText.length - lineText.trimStart().length,
      diagLine,
      lineText.length
    );

    const diag = new vscode.Diagnostic(
      range,
      `Sequent: ${func.consensus}`,
      severity
    );
    diag.source = "sequent";
    diag.code = func.name;

    // Attach counterexample details as related information
    if (func.z3?.counterexamples) {
      const relatedInfo: vscode.DiagnosticRelatedInformation[] = [];
      for (const cx of func.z3.counterexamples) {
        const cxLine =
          cx.line !== null && cx.line > 0 ? cx.line - 1 : funcLine;
        const loc = new vscode.Location(
          document.uri,
          new vscode.Position(cxLine, 0)
        );
        const cxStr = JSON.stringify(cx.counterexample);
        relatedInfo.push(
          new vscode.DiagnosticRelatedInformation(
            loc,
            `${cx.property}: ${cx.description} [counterexample: ${cxStr}]`
          )
        );
      }
      diag.relatedInformation = relatedInfo;
    }

    diagnostics.push(diag);
  }

  diagnosticCollection.set(document.uri, diagnostics);

  // Update status bar
  const parts: string[] = [];
  if (verifiedCount > 0) {
    parts.push(`$(check) ${verifiedCount} verified`);
  }
  if (bugCount > 0) {
    parts.push(`$(warning) ${bugCount} bug${bugCount > 1 ? "s" : ""}`);
  }

  if (parts.length > 0) {
    statusBarItem.text = `$(shield) Sequent: ${parts.join(" | ")}`;
  } else {
    statusBarItem.text = "$(shield) Sequent";
  }
}

/**
 * Find the 0-indexed line number of a top-level `def funcName(` in the document.
 */
function findFunctionLine(
  document: vscode.TextDocument,
  funcName: string
): number {
  const pattern = new RegExp(`^\\s*def\\s+${escapeRegExp(funcName)}\\s*\\(`);
  for (let i = 0; i < document.lineCount; i++) {
    if (pattern.test(document.lineAt(i).text)) {
      return i;
    }
  }
  return -1;
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// ---------------------------------------------------------------------------
// Hover provider
// ---------------------------------------------------------------------------

function provideSequentHover(
  document: vscode.TextDocument,
  position: vscode.Position
): vscode.Hover | undefined {
  const lineText = document.lineAt(position.line).text;
  const defMatch = lineText.match(/^\s*def\s+(\w+)\s*\(/);
  if (!defMatch) {
    return undefined;
  }

  const funcName = defMatch[1];
  const cached = certCache.get(document.uri.toString());
  if (!cached) {
    return undefined;
  }

  const func = cached.find((f) => f.name === funcName);
  if (!func) {
    return undefined;
  }

  const md = new vscode.MarkdownString();
  md.isTrusted = true;

  if (func.verdict === "verified") {
    md.appendMarkdown(`**Sequent: Verified** $(check)\n\n`);
  } else {
    md.appendMarkdown(`**Sequent: Bug Detected**\n\n`);
    md.appendMarkdown(`${func.consensus}\n\n`);
  }

  if (func.gnn) {
    const pct = (func.gnn.confidence * 100).toFixed(1);
    md.appendMarkdown(
      `**GNN:** ${func.gnn.prediction} (${pct}% confidence)\n\n`
    );
    if (func.gnn.suspect_lines && func.gnn.suspect_lines.length > 0) {
      md.appendMarkdown(
        `Suspect lines: ${func.gnn.suspect_lines.join(", ")}\n\n`
      );
    }
  }

  if (func.z3) {
    md.appendMarkdown(
      `**Z3:** ${func.z3.result} (${func.z3.properties_checked} properties, ` +
        `${func.z3.properties_verified} verified)\n\n`
    );
    if (func.z3.counterexamples && func.z3.counterexamples.length > 0) {
      md.appendMarkdown("**Counterexamples:**\n\n");
      for (const cx of func.z3.counterexamples) {
        md.appendCodeBlock(
          `${cx.property}: ${cx.description}\n` +
            JSON.stringify(cx.counterexample, null, 2),
          "json"
        );
      }
    }
  }

  md.appendMarkdown(`\n*${func.time_ms.toFixed(0)}ms*`);

  return new vscode.Hover(md);
}

// ---------------------------------------------------------------------------
// Code action provider (Quick Fix for auto-repair)
// ---------------------------------------------------------------------------

class SequentCodeActionProvider implements vscode.CodeActionProvider {
  static readonly providedCodeActionKinds = [vscode.CodeActionKind.QuickFix];

  provideCodeActions(
    document: vscode.TextDocument,
    range: vscode.Range | vscode.Selection,
    context: vscode.CodeActionContext
  ): vscode.CodeAction[] {
    const actions: vscode.CodeAction[] = [];

    for (const diag of context.diagnostics) {
      if (diag.source !== "sequent") {
        continue;
      }

      const funcName = diag.code as string;
      const cached = certCache.get(document.uri.toString());
      if (!cached) {
        continue;
      }

      const func = cached.find((f) => f.name === funcName);
      if (!func?.repair?.repaired_code) {
        continue;
      }

      const title = func.repair.verified
        ? `Sequent: Apply verified fix -- ${func.repair.description}`
        : `Sequent: Apply fix (unverified) -- ${func.repair.description}`;

      const action = new vscode.CodeAction(title, vscode.CodeActionKind.QuickFix);
      action.diagnostics = [diag];
      action.isPreferred = func.repair.verified;

      // Build a workspace edit that replaces the entire function body
      const funcLine = findFunctionLine(document, funcName);
      if (funcLine < 0) {
        continue;
      }

      // Find the end of the function (next top-level def/class or EOF)
      let endLine = document.lineCount - 1;
      for (let i = funcLine + 1; i < document.lineCount; i++) {
        const text = document.lineAt(i).text;
        if (/^\S/.test(text) && text.trim().length > 0) {
          endLine = i - 1;
          break;
        }
      }

      const replaceRange = new vscode.Range(
        funcLine,
        0,
        endLine,
        document.lineAt(endLine).text.length
      );

      const edit = new vscode.WorkspaceEdit();
      edit.replace(document.uri, replaceRange, func.repair.repaired_code);
      action.edit = edit;

      actions.push(action);
    }

    return actions;
  }
}

// ---------------------------------------------------------------------------
// Auto-repair command (triggered from command palette or code action)
// ---------------------------------------------------------------------------

async function applyRepair(
  uri: vscode.Uri,
  funcName: string
): Promise<void> {
  const cached = certCache.get(uri.toString());
  if (!cached) {
    vscode.window.showInformationMessage(
      "Sequent: No verification results available. Run verification first."
    );
    return;
  }

  const func = cached.find((f) => f.name === funcName);
  if (!func?.repair?.repaired_code) {
    vscode.window.showInformationMessage(
      `Sequent: No repair available for '${funcName}'.`
    );
    return;
  }

  const document = await vscode.workspace.openTextDocument(uri);
  const funcLine = findFunctionLine(document, funcName);
  if (funcLine < 0) {
    return;
  }

  let endLine = document.lineCount - 1;
  for (let i = funcLine + 1; i < document.lineCount; i++) {
    const text = document.lineAt(i).text;
    if (/^\S/.test(text) && text.trim().length > 0) {
      endLine = i - 1;
      break;
    }
  }

  const replaceRange = new vscode.Range(
    funcLine,
    0,
    endLine,
    document.lineAt(endLine).text.length
  );

  const edit = new vscode.WorkspaceEdit();
  edit.replace(uri, replaceRange, func.repair.repaired_code);
  await vscode.workspace.applyEdit(edit);

  vscode.window.showInformationMessage(
    `Sequent: Applied repair for '${funcName}': ${func.repair.description}`
  );
}
