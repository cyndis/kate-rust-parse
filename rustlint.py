# kate: space-indent on; indent-width 4;

import subprocess
import re
import json
import os.path

def findCargoProjectDir(url):
    dir = url.directory()

    if os.path.isfile(dir + "/Cargo.toml") or os.path.isfile(dir + "/cargo.toml"):
        return dir
    else:
        up = url.upUrl()
        if up == url:
            return None
        return findCargoProjectDir(up)

def getCargoData(url):
    if not url.isLocalFile():
        return None

    dir = findCargoProjectDir(url)
    if not dir:
        return None

    cargo_proc = subprocess.Popen(["cargo", "read-manifest", "--manifest-path="+dir],
                                    stdout=subprocess.PIPE)
    out, _ = cargo_proc.communicate()

    manifest = json.loads(out.decode('utf-8'))

    main_target = manifest["targets"][0]

    data = {
        "is_lib": main_target["kind"] == ["lib"],
        "dep_path": dir + "/target/deps",
        "root": main_target["src_path"]
    }

    return data

class RustError:
    def __init__(self, filename, line, message):
        self.filename = filename
        self.line = line
        self.message = message

PARSE_ERROR_RE = re.compile(r"<anon>:(\d+):(\d+):.* error: (.+)")
def rustParseString(s):
    process = subprocess.Popen(["rustc", "--parse-only", "-"], 0, None, subprocess.PIPE, None,
                               subprocess.PIPE)
    _, err = process.communicate(s)

    error_lines = []

    lines = err.decode('utf-8').split("\n")
    for line in lines:
        match = PARSE_ERROR_RE.findall(line)
        if match:
            match = match[0]
            if "file not found for module" in match[2]:
                continue
            error_lines.append(RustError(None, int(match[0]), match[2].strip()))

    return error_lines

COMPILE_ERROR_RE = re.compile(r"([^:]+):(\d+):(\d+):.*\serror: (.+)")
COMPILE_ERROR_NOLINE_RE = re.compile(r"^error: (.+)")
def rustTypecheckFile(url):
    cargo_data = getCargoData(url)

    args = ["rustc", "--no-trans"]
    if cargo_data:
        if cargo_data["is_lib"]:
            args.append("--crate-type")
            args.append("lib")
        args.append("-L" + cargo_data["dep_path"])
        args.append(cargo_data["root"])
    else:
        args.append(url.pathOrUrl())

    process = subprocess.Popen(args, 0, None, None, None, subprocess.PIPE)
    _, err = process.communicate()

    error_lines = []

    lines = err.decode('utf-8').split("\n")
    for line in lines:
        match = COMPILE_ERROR_RE.findall(line)
        if match:
            match = match[0]
            error_lines.append(RustError(match[0], int(match[1]), match[3].strip()))
        else:
            match = COMPILE_ERROR_NOLINE_RE.findall(line)
            if match:
                if cargo_data:
                    fn = cargo_data["root"]
                else:
                    fn = None
                error_lines.append(RustError(fn, None, match[0].strip()))

    return error_lines

import kate
import kate.view
from libkatepate.errors import showOk, showErrors, clearMarksOfError

global documentLastErrors
documentLastErrors = {}

COMPILE_ERR = 1
PARSE_ERR = 0
def getDocumentErrorKey(doc, typ):
    if typ == PARSE_ERR:
        return doc
    else:
        cargo_dir = findCargoProjectDir(doc.url())
        if cargo_dir:
            return cargo_dir
        else:
            return doc

def cleanupDocErrors(doc):
    pkey = getDocumentErrorKey(doc, PARSE_ERR)
    if pkey in documentLastErrors:
        del documentLastErrors[pkey]
    # ckey might be in use by another document.. just leave them there.
    # there's just one per cargo project anyway.

def setDocErrors(doc, typ, errors):
    mark_iface = doc.markInterface()

    if typ == PARSE_ERR:
        for line in range(doc.lines()):
            if mark_iface.mark(line) == mark_iface.Error:
                mark_iface.removeMark(line, mark_iface.Error)

    key = getDocumentErrorKey(doc, typ)

    if not key in documentLastErrors:
        documentLastErrors[key] = {COMPILE_ERR: [], PARSE_ERR: []}
        doc.aboutToClose.connect(cleanupDocErrors)
    documentLastErrors[key][typ] = errors

    updateErrlist()

    if typ == PARSE_ERR and len(errors) > 0:
        for error in errors:
            if error.line:
                mark_iface.setMark(error.line - 1, mark_iface.Error)

@kate.viewChanged
def updateErrlist(view=None, *args, **kwargs):
    view = view or kate.activeView()
    if not view:
        return

    parseErrorWidget.clear()
    compileErrorWidget.clear()

    doc = view.document()
    pkey = getDocumentErrorKey(doc, PARSE_ERR)
    ckey = getDocumentErrorKey(doc, COMPILE_ERR)

    if pkey in documentLastErrors:
        for error in documentLastErrors[pkey][PARSE_ERR]:
            if error.line:
                parseErrorWidget.addItem("line " + str(error.line) + ": " + error.message)
            else:
                parseErrorWidget.addItem(error.message)

    if ckey in documentLastErrors:
        for error in documentLastErrors[ckey][COMPILE_ERR]:
            msg = ""
            if error.filename:
                msg = msg + error.filename + ": "
            if error.line:
                msg = msg + "line " + str(error.line) + ": "
            compileErrorWidget.addItem(msg + error.message)

def lintRust():
    doc = kate.activeDocument()

    text = doc.text().encode('utf-8', 'ignore')
    errors = rustParseString(text)

    setDocErrors(doc, PARSE_ERR, errors)

def autoLintRust():
    doc = kate.activeDocument()
    if doc.highlightingMode() != "Rust":
        return

    lintRust()

def typecheckRust():
    doc = kate.activeDocument()

    errors = rustTypecheckFile(doc.url())

    setDocErrors(doc, COMPILE_ERR, errors)

def autoTypecheckRust():
    doc = kate.activeDocument()
    if doc.highlightingMode() == "Rust" and doc.url().isLocalFile():
        typecheckRust()

@kate.viewCreated
def createSignalCheckDocument(view=None, *args, **kwargs):
    view = view or kate.activeView()
    doc = view.document()
    doc.textChanged.connect(autoLintRust)
    doc.documentSavedOrUploaded.connect(autoTypecheckRust)

from PyKDE4.kdecore import *
from PyKDE4.kdeui import *
from PyQt4.QtGui import *

@kate.init
def initRustlint():
    msgview = kate.mainInterfaceWindow().createToolView("rustlint_plugin",
                                                        kate.Kate.MainWindow.Bottom,
                                                        SmallIcon("task-attention"),
                                                        "Rust Errors")

    parent = QWidget(msgview)
    box = QHBoxLayout()
    parent.setLayout(box)

    global parseErrorWidget
    parseErrorWidget = KListWidget()
    box.addWidget(parseErrorWidget)

    global compileErrorWidget
    compileErrorWidget = KListWidget()
    box.addWidget(compileErrorWidget)
