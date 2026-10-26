#!/usr/bin/env python3
# CODEX v2 - Termux AI Code Engine
# Guarda a chave da API em ~/codex/.apikey. Nunca compartilhe esse arquivo.

import os
import sys
import json
import re
import time
import shutil
import difflib
import subprocess
import urllib.request
import urllib.error

BASE = os.path.expanduser("~/codex")
PROJ = os.path.join(BASE, "projects")
BAK = os.path.join(BASE, "backups")
KEYF = os.path.join(BASE, ".apikey")
OUT = "/sdcard/Codex"
MODEL = "gemini-3.5-flash-lite"
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

R = "\033[0m"
B = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
DRED = "\033[31m"
GRN = "\033[92m"
YEL = "\033[93m"
CYN = "\033[96m"
GRY = "\033[90m"
WHT = "\033[97m"
MAG = "\033[95m"

SYSTEM = (
    "You are Codex, a software engineer helping a user on Android Termux. "
    "Return one complete working file only. First line must be exactly "
    "'FILENAME: name.ext', then one fenced code block containing the entire file. "
    "For HTML, use one file with inline CSS and JavaScript and a mobile-friendly UI. "
    "For Python, prefer the standard library. For C++, use C++17. "
    "Do not omit required code or use placeholders."
)

BANNER = r"""
  ██████╗ ██████╗ ██████╗ ███████╗██╗  ██╗
 ██╔════╝██╔═══██╗██╔══██╗██╔════╝╚██╗██╔╝
 ██║     ██║   ██║██║  ██║█████╗   ╚███╔╝
 ██║     ██║   ██║██║  ██║██╔══╝   ██╔██╗
 ╚██████╗╚████╔╝██████╔╝███████╗██╔╝ ██╗
  ╚═════╝ ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═╝
"""

STATS = {"runs": 0, "lines": 0, "fixes": 0, "start": time.time()}


def w(text):
    sys.stdout.write(str(text))
    sys.stdout.flush()


def clear():
    os.system("clear")


def banner():
    clear()
    w(RED + B + BANNER + R)
    w(DRED + " ══════════════════════════════════════════\n" + R)
    w(GRY + " [ AI CODE ENGINE v2 ]  " + RED + MODEL + R + "\n")
    w(DRED + " ══════════════════════════════════════════\n" + R)
    w(GRY + " /new /paste /open /show /edit /fix /run\n"
      " /save /undo /list /stats /key /help /quit\n\n" + R)


def get_key():
    os.makedirs(BASE, exist_ok=True)
    if os.path.exists(KEYF):
        try:
            key = open(KEYF, encoding="utf-8").read().strip()
            if key:
                return key
        except OSError:
            pass
    key = input(RED + "[?] Cole sua API key do Gemini: " + R).strip()
    if not key:
        print(RED + "A chave não pode ficar vazia." + R)
        return get_key()
    with open(KEYF, "w", encoding="utf-8") as f:
        f.write(key)
    try:
        os.chmod(KEYF, 0o600)
    except OSError:
        pass
    return key


def ask_ai(history, key):
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM}]},
        "contents": history,
        "generationConfig": {"temperature": 0.25, "maxOutputTokens": 8192},
    }
    request = urllib.request.Request(
        API_URL.format(model=MODEL),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            data = json.loads(response.read().decode("utf-8"))
        candidates = data.get("candidates", [])
        if not candidates:
            return None, "A API não retornou uma resposta. Confira o modelo e os limites da API."
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(p.get("text", "") for p in parts)
        if not text.strip():
            return None, "A resposta da API veio vazia."
        return text, None
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", "ignore")[:1200]
        if exc.code in (401, 403):
            return None, "A API recusou a chave/permissão (HTTP %s). Confira a chave e o acesso ao modelo.\n%s" % (exc.code, details)
        if exc.code == 404:
            return None, "Modelo não encontrado (HTTP 404). Confira o nome do modelo configurado.\n%s" % details
        if exc.code == 429:
            return None, "Limite de uso da API atingido (HTTP 429). Confira cota e faturamento.\n%s" % details
        return None, "Erro HTTP %s:\n%s" % (exc.code, details)
    except Exception as exc:
        return None, "Falha de conexão: %s" % exc


def extract(response):
    name_match = re.search(r"(?im)^\s*FILENAME:\s*([A-Za-z0-9_.-]+)", response)
    name = name_match.group(1) if name_match else "output.txt"
    name = os.path.basename(name)
    code_match = re.search(r"```[^\n]*\n(.*?)```", response, re.S)
    code = code_match.group(1) if code_match else response
    return name, code.rstrip() + "\n"


def show_file(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError as exc:
        print(RED + str(exc) + R)
        return
    print(DRED + "╭─ " + WHT + os.path.basename(path) + GRY +
          " (%s linhas)" % len(lines) + R)
    for number, line in enumerate(lines, 1):
        print(GRY + "%4d " % number + R + WHT + line + R)
    print(DRED + "╰" + "─" * 30 + R)


def backup(path):
    if not os.path.isfile(path):
        return None
    os.makedirs(BAK, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    destination = os.path.join(BAK, "%s.%s.bak" % (os.path.basename(path), stamp))
    shutil.copy2(path, destination)
    return destination


def export_file(path):
    try:
        os.makedirs(OUT, exist_ok=True)
        destination = os.path.join(OUT, os.path.basename(path))
        shutil.copy2(path, destination)
        print(GRN + "Exportado para: " + destination + R)
        return True
    except Exception as exc:
        print(YEL + "Não consegui exportar para /sdcard/Codex: " + str(exc) + R)
        print(YEL + "Se necessário, execute: termux-setup-storage" + R)
        return False


def check_file(path):
    extension = os.path.splitext(path)[1].lower()
    if extension == ".py":
        result = subprocess.run(
            [sys.executable, "-m", "py_compile", path],
            capture_output=True, text=True
        )
        return result.returncode == 0, result.stderr or result.stdout
    if extension == ".cpp":
        compiler = shutil.which("clang++")
        if not compiler:
            return False, "clang++ não instalado. Instale com: pkg install clang"
        result = subprocess.run(
            [compiler, "-std=c++17", "-fsyntax-only", "-Wall", path],
            capture_output=True, text=True
        )
        return result.returncode == 0, result.stderr or result.stdout
    if extension in (".html", ".htm"):
        with open(path, encoding="utf-8", errors="replace") as f:
            source = f.read().lower()
        issues = []
        if "<html" not in source:
            issues.append("Tag <html> não encontrada.")
        for tag in ("html", "head", "body", "script", "style"):
            opening = len(re.findall(r"<" + tag + r"(?:\s|>)", source))
            closing = source.count("</" + tag + ">")
            if opening != closing:
                issues.append("Tags <%s> desequilibradas (%d abertas, %d fechadas)." %
                              (tag, opening, closing))
        return not issues, "\n".join(issues)
    return True, ""


def build_file(path):
    extension = os.path.splitext(path)[1].lower()
    if extension == ".py":
        # Não executa automaticamente o arquivo gerado: isso poderia fazer
        # alterações indesejadas no aparelho. A verificação de sintaxe é feita acima.
        return True, "Python: sintaxe verificada; execução manual pelo comando /run."
    if extension == ".cpp":
        compiler = shutil.which("clang++")
        if not compiler:
            return False, "clang++ não instalado. Instale com: pkg install clang"
        executable = os.path.splitext(path)[0]
        result = subprocess.run(
            [compiler, "-std=c++17", "-Wall", path, "-o", executable],
            capture_output=True, text=True
        )
        return result.returncode == 0, result.stderr or result.stdout
    return True, ""


def run_file(path):
    if not path or not os.path.isfile(path):
        print(YEL + "Abra ou crie um arquivo primeiro." + R)
        return
    extension = os.path.splitext(path)[1].lower()
    print(CYN + "[EXEC] " + os.path.basename(path) + R)
    try:
        if extension == ".py":
            subprocess.call([sys.executable, path])
        elif extension == ".cpp":
            executable = os.path.splitext(path)[0]
            if not os.path.isfile(executable):
                ok, log = build_file(path)
                if not ok:
                    print(RED + log + R)
                    return
            subprocess.call([executable])
        elif extension in (".html", ".htm"):
            opener = shutil.which("termux-open")
            if opener:
                subprocess.call([opener, path])
            else:
                print(YEL + "termux-open não encontrado. Instale o pacote termux-tools." + R)
        else:
            print(YEL + "Tipo de arquivo não executável por este painel." + R)
    except Exception as exc:
        print(RED + str(exc) + R)


def read_multiline(prompt):
    print(YEL + prompt + R)
    print(GRY + "Cole o texto. Para terminar, digite END sozinho em uma linha." + R)
    lines = []
    while True:
        try:
            line = input()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines) + "\n"


def generate(history, key, old_code=None):
    print(CYN + "Consultando Gemini..." + R)
    answer, error = ask_ai(history, key)
    if error:
        print(RED + error + R)
        return None
    name, code = extract(answer)
    if not name or name in (".", ".."):
        name = "output.txt"
    os.makedirs(PROJ, exist_ok=True)
    path = os.path.join(PROJ, name)
    if os.path.exists(path):
        backup(path)
    if old_code is not None:
        print(DRED + "╭─ DIFERENÇAS" + R)
        for line in difflib.unified_diff(
            old_code.splitlines(), code.splitlines(),
            fromfile="antes", tofile="depois", lineterm=""
        ):
            print((GRN if line.startswith("+") else RED if line.startswith("-") else GRY) + line + R)
        print(DRED + "╰" + R)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    history.append({"role": "model", "parts": [{"text": answer}]})
    STATS["runs"] += 1
    STATS["lines"] += len(code.splitlines())
    print(GRN + "Arquivo salvo: " + path + R)
    ok, log = check_file(path)
    if ok:
        print(GRN + "✔ Verificação de sintaxe concluída." + R)
    else:
        print(YEL + "⚠ Verificação encontrou possíveis erros:\n" + log + R)
    if os.path.splitext(path)[1].lower() == ".cpp":
        built, build_log = build_file(path)
        print((GRN if built else RED) + ("✔ Compilado." if built else "Falha na compilação.") + R)
        if build_log:
            print(build_log)
    export_file(path)
    return path


def show_stats():
    uptime = int(time.time() - STATS["start"])
    print(DRED + "╭─ ESTATÍSTICAS" + R)
    print("Criações: %d | Linhas geradas: %d | Correções: %d | Tempo: %ds" %
          (STATS["runs"], STATS["lines"], STATS["fixes"], uptime))
    print(DRED + "╰" + R)


def help_text():
    print(CYN + "Comandos do CODEX v2" + R)
    print("/new              Limpa o contexto da conversa")
    print("/paste            Salva um código que você colar")
    print("/open arquivo     Abre um arquivo da pasta projects")
    print("/show [arquivo]   Mostra o arquivo atual ou informado")
    print("/edit pedido      Edita o arquivo atual com IA")
    print("/fix              Pede à IA para corrigir o arquivo atual")
    print("/run              Executa o arquivo atual")
    print("/save             Exporta o arquivo para /sdcard/Codex")
    print("/undo             Restaura o backup mais recente do arquivo atual")
    print("/list             Lista os arquivos do projeto")
    print("/stats            Mostra estatísticas")
    print("/key              Troca a chave da API")
    print("/help             Mostra esta ajuda")
    print("/quit             Fecha o painel")
    print("Para criar algo, escreva o pedido normalmente.")


def main():
    os.makedirs(PROJ, exist_ok=True)
    os.makedirs(BAK, exist_ok=True)
    key = get_key()
    banner()
    history = []
    current = None

    while True:
        try:
            user_input = input(RED + B + "codex" + R + GRY + "@termux" + R +
                               RED + " ❯ " + R).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue

        command, _, argument = user_input.partition(" ")
        command = command.lower()
        argument = argument.strip()

        if command == "/quit":
            break
        elif command == "/help":
            help_text()
        elif command == "/new":
            history = []
            current = None
            print(GRN + "Nova conversa iniciada." + R)
        elif command == "/stats":
            show_stats()
        elif command == "/key":
            try:
                if os.path.exists(KEYF):
                    os.remove(KEYF)
            except OSError as exc:
                print(RED + str(exc) + R)
            key = get_key()
        elif command == "/list":
            files = sorted(os.listdir(PROJ))
            if not files:
                print(YEL + "Nenhum arquivo ainda." + R)
            for filename in files:
                filepath = os.path.join(PROJ, filename)
                if os.path.isfile(filepath):
                    print(CYN + filename + R + GRY + " (%d bytes)" % os.path.getsize(filepath) + R)
        elif command == "/show":
            path = current if not argument else (
                argument if os.path.isabs(argument) else os.path.join(PROJ, os.path.basename(argument))
            )
            if path:
                show_file(path)
            else:
                print(YEL + "Nenhum arquivo selecionado." + R)
        elif command == "/run":
            run_file(current)
        elif command == "/save":
            if current and os.path.isfile(current):
                export_file(current)
            else:
                print(YEL + "Nenhum arquivo selecionado." + R)
        elif command == "/open":
            if not argument:
                print(YEL + "Use: /open nome_do_arquivo" + R)
                continue
            path = argument if os.path.isabs(argument) else os.path.join(PROJ, os.path.basename(argument))
            if os.path.isfile(path):
                current = path
                history = []
                print(GRN + "Aberto: " + path + R)
                show_file(path)
            else:
                print(RED + "Arquivo não encontrado: " + path + R)
        elif command == "/paste":
            code = read_multiline("Cole seu código")
            filename = input("Nome do arquivo (ex.: app.py): ").strip() or "pasted.py"
            filename = os.path.basename(filename)
            current = os.path.join(PROJ, filename)
            if os.path.exists(current):
                backup(current)
            with open(current, "w", encoding="utf-8") as f:
                f.write(code)
            print(GRN + "Salvo: " + current + R)
            show_file(current)
        elif command == "/undo":
            if not current:
                print(YEL + "Abra um arquivo primeiro." + R)
                continue
            prefix = os.path.basename(current) + "."
            backups = sorted(
                f for f in os.listdir(BAK)
                if f.startswith(prefix) and f.endswith(".bak")
            )
            if not backups:
                print(YEL + "Nenhum backup encontrado." + R)
                continue
            latest = os.path.join(BAK, backups[-1])
            shutil.copy2(latest, current)
            os.remove(latest)
            print(GRN + "Backup restaurado: " + backups[-1] + R)
        elif command in ("/edit", "/fix"):
            if not current or not os.path.isfile(current):
                print(YEL + "Abra um arquivo com /open ou crie um primeiro." + R)
                continue
            with open(current, encoding="utf-8", errors="replace") as f:
                old_code = f.read()
            if command == "/fix":
                ok, log = check_file(current)
                if ok:
                    print(GRN + "Nenhum erro de sintaxe detectado." + R)
                    print("Se houver um erro de execução, descreva-o com /edit.")
                    continue
                prompt = "Corrija o arquivo completo abaixo. Erros encontrados:\n%s\n\nCódigo atual:\n%s" % (log, old_code)
                STATS["fixes"] += 1
            else:
                prompt = "Edite o arquivo completo conforme este pedido: %s\n\nCódigo atual:\n%s" % (argument, old_code)
            history.append({"role": "user", "parts": [{"text": prompt}]})
            result = generate(history, key, old_code)
            if result:
                current = result
        else:
            history.append({"role": "user", "parts": [{"text": user_input}]})
            result = generate(history, key)
            if result:
                current = result
            else:
                # Evita deixar uma mensagem sem resposta na próxima tentativa.
                history.pop()

    print(GRY + "CODEX encerrado." + R)


if __name__ == "__main__":
    main()
