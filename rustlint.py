# kate: space-indent on; indent-width 4;

import subprocess
import re

ERROR_RE = re.compile(r"<anon>:(\d+):(\d+):.*error: (.+)")

def parseCheckString(s):
    process = subprocess.Popen(["rustc", "--parse-only", "-"], 0, None, subprocess.PIPE, None,
                               subprocess.PIPE)
    _, err = process.communicate(s)

    error_lines = []

    lines = err.decode('utf-8').split("\n")
    for line in lines:
        match = ERROR_RE.findall(line)
        if match:
            match = match[0]
            error_lines.append([int(match[0]), match[2].strip()])

    return error_lines

import kate
import kate.view
from libkatepate.errors import showOk, showErrors, clearMarksOfError

global docerrors
docerrors = {}

def cleanupDocErrors(doc):
    del docerrors[doc]

def showParseErrors(doc):
    text = doc.text().encode('utf-8', 'ignore')
    perrors = parseCheckString(text)

    mark_iface = doc.markInterface()

    for line in range(doc.lines()):
        if mark_iface.mark(line) == mark_iface.Error:
            mark_iface.removeMark(line, mark_iface.Error)

    if not doc in docerrors:
        doc.aboutToClose.connect(cleanupDocErrors)
    docerrors[doc] = perrors

    updateErrlist()

    if len(perrors) == 0:
        return

    errors = []
    for error in perrors:
        mark_iface.setMark(error[0]-1, mark_iface.Error)

@kate.action
def lintRust():
    doc = kate.activeDocument()
    showParseErrors(doc)

def autoLintRust():
    doc = kate.activeDocument()
    if doc.highlightingMode() != "Rust":
        return

    lintRust()

@kate.viewChanged
def updateErrlist(view=None, *args, **kwargs):
    print("viewChanged")
    view = view or kate.activeView()
    if not view:
        return

    doc = view.document()
    if not doc in docerrors:
        return

    global errlist
    errlist.clear()

    for error in docerrors[doc]:
        errlist.addItem("Line " + str(error[0]) + ": " + error[1])

@kate.viewCreated
def createSignalCheckDocument(view=None, *args, **kwargs):
    view = view or kate.activeView()
    doc = view.document()
    doc.textChanged.connect(autoLintRust)

from PyKDE4.kdecore import *
from PyKDE4.kdeui import *

@kate.init
def initRustlint():
    msgview = kate.mainInterfaceWindow().createToolView("rustlint_plugin",
                                                        kate.Kate.MainWindow.Bottom,
                                                        SmallIcon("task-attention"),
                                                        "Rust Parse Errors")
    global errlist
    errlist = KListWidget(msgview)
