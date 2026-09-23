import os
import re
import shlex
import subprocess
from app.services.util import as_bool

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

_BLOQUEIO = (
    r"\bformat(\.com|\.exe)?\b",
    r"\bdiskpart\b",
    r"\bshutdown(\.exe)?\b",
    r"\bbcdedit\b",
    r"\bcipher\s+/w",
    r"\breg(\.exe)?\s+delete\b",
    r"\b(rd|rmdir)\s+/s\b",
    r"\bdel\s+/[sfq]",
    r"\berase\s+/[sfq]",
    r"\brm\s+-[rf]",
    r"\bmkfs\b",
    r"\bdd\s+if=",
    r"\bnet\s+user\b.*(/add|/delete|/active)",
    r"\bnet\s+localgroup\b",
    r"\bpowershell\b.*(-e(nc|ncodedcommand)\b|iex\b|invoke-expression)",
    r"\b(iex|invoke-expression)\b",
    r"\|\s*(iex|invoke-expression)\b",
    r"\bschtasks\b",
    r"\bvssadmin\s+delete\b",
    r"\bwbadmin\b",
    r"\bfsutil\b",
    r"\btakeown\b",
    r"\bicacls\b",
    r"\bnetsh\s+advfirewall\b",
    r"\bsc(\.exe)?\s+(delete|stop)\b",
)

_CMD_BUILTIN = {
    "assoc", "break", "call", "cd", "chdir", "cls", "color", "copy", "date",
    "del", "dir", "echo", "endlocal", "erase", "exit", "for", "ftype", "goto",
    "if", "md", "mkdir", "mklink", "move", "path", "pause", "popd", "prompt",
    "pushd", "rd", "rem", "ren", "rename", "rmdir", "set", "setlocal", "shift",
    "start", "time", "title", "type", "ver", "verify", "vol",
}

_METACHAR = set("|><&()%^")


class ShellService:
    def executar_comando(self, cmd, confirmado=False):
        if not as_bool(confirmado):
            return f"Confirmação necessária para executar: '{cmd}'"
        if not cmd or not str(cmd).strip():
            return "Comando vazio."
        bruto = str(cmd).strip()
        if self._bloqueado(bruto):
            return "Recusado: comando destrutivo ou perigoso."
        try:
            argv = self._argv(bruto)
            kwargs = {
                "args": argv,
                "capture_output": True,
                "text": True,
                "timeout": 15,
                "shell": False,
            }
            if os.name == "nt":
                kwargs["creationflags"] = _CREATE_NO_WINDOW
            resultado = subprocess.run(**kwargs)
            saida = resultado.stdout.strip() or resultado.stderr.strip() or "Comando executado sem saída."
            return saida[:600]
        except subprocess.TimeoutExpired:
            return "Timeout: comando demorou mais de 15 segundos."
        except FileNotFoundError:
            return f"Executável não encontrado: {bruto.split()[0]}"
        except Exception as e:
            return f"Erro ao executar: {e}"

    def _bloqueado(self, cmd):
        texto = cmd.lower()
        return any(re.search(pat, texto, re.IGNORECASE) for pat in _BLOQUEIO)

    def _argv(self, cmd):
        if os.name != "nt":
            return shlex.split(cmd)
        if self._precisa_cmd(cmd):
            return ["cmd.exe", "/c", cmd]
        return shlex.split(cmd, posix=False)

    def _precisa_cmd(self, cmd):
        if any(ch in cmd for ch in _METACHAR) or "*" in cmd or "?" in cmd:
            return True
        try:
            partes = shlex.split(cmd, posix=False)
        except ValueError:
            return True
        if not partes:
            return True
        primeiro = os.path.basename(partes[0]).lower()
        if primeiro.endswith(".exe"):
            primeiro = primeiro[:-4]
        return primeiro in _CMD_BUILTIN
