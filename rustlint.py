# kate: space-indent on; indent-width 4;

import subprocess
import re

class RustError:
    def __init__(self, line, message):
        self.line = line
        self.message = message

PARSE_ERROR_RE = re.compile(r"<anon>:(\d+):(\d+):.*error: (.+)")
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
            error_lines.append(RustError(int(match[0]), match[2].strip()))

    return error_lines

COMPILE_ERROR_RE = re.compile(r"[^:]+:(\d+):(\d+):.*error: (.+)")
COMPILE_ERROR_NOLINE_RE = re.compile(r"error: (.+)")
def rustTypecheckFile(url):
    process = subprocess.Popen(["rustc", "--no-trans", url.pathOrUrl()], 0, None, None,
                               None, subprocess.PIPE)
    _, err = process.communicate()

    error_lines = []

    lines = err.decode('utf-8').split("\n")
    for line in lines:
        match = COMPILE_ERROR_RE.findall(line)
        if match:
            match = match[0]
            error_lines.append(RustError(int(match[0]), match[2].strip()))
        else:
            match = COMPILE_ERROR_NOLINE_RE.findall(line)
            if match:
                error_lines.append(RustError(None, match[0].strip()))

    return error_lines

import kate
import kate.view
from libkatepate.errors import showOk, showErrors, clearMarksOfError

global documentLastErrors
documentLastErrors = {}

def cleanupDocErrors(doc):
    del documentLastErrors[doc]

COMPILE_ERR = 1
PARSE_ERR = 0
def setDocErrors(doc, typ, errors):
    mark_iface = doc.markInterface()

    if typ == PARSE_ERR:
        for line in range(doc.lines()):
            if mark_iface.mark(line) == mark_iface.Error:
                mark_iface.removeMark(line, mark_iface.Error)

    if not doc in documentLastErrors:
        documentLastErrors[doc] = {COMPILE_ERR: [], PARSE_ERR: []}
        doc.aboutToClose.connect(cleanupDocErrors)
    documentLastErrors[doc][typ] = errors

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
    if not doc in documentLastErrors:
        return

    for error in documentLastErrors[doc][PARSE_ERR]:
        if error.line:
            parseErrorWidget.addItem("Line " + str(error.line) + ": " + error.message)
        else:
            parseErrorWidget.addItem(error.message)

    for error in documentLastErrors[doc][COMPILE_ERR]:
        if error.line:
            compileErrorWidget.addItem("Line " + str(error.line) + ": " + error.message)
        else:
            compileErrorWidget.addItem("Error: " + error.message)

@kate.action
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
                                                        "Rust Parse Errors")

    parent = QWidget(msgview)
    box = QHBoxLayout()
    parent.setLayout(box)

    global parseErrorWidget
    parseErrorWidget = KListWidget()
    box.addWidget(parseErrorWidget)

    global compileErrorWidget
    compileErrorWidget = KListWidget()
    box.addWidget(compileErrorWidget)
