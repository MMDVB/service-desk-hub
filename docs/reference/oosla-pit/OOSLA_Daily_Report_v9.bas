Attribute VB_Name = "OOSLA_Daily_Report"
Option Explicit

Public Sub GenerateDailyOOSLAReport()

    Dim wb As Workbook, src As Worksheet
    Dim mainWs As Worksheet, nwgWs As Worksheet, otherWs As Worksheet
    Dim lastRow As Long, r As Long, c As Long
    Dim status As String, grp As String
    Dim nwgRow As Long, otherRow As Long
    Dim hdr As Variant

    Set wb = ThisWorkbook
    Set src = ActiveSheet

    Application.ScreenUpdating = False
    Application.EnableEvents = False
    Application.DisplayAlerts = False

    On Error GoTo CleanFail

    DeleteSheetIfExists wb, "ITS OOSLA INCs"
    DeleteSheetIfExists wb, "NWG & CT INCs"
    DeleteSheetIfExists wb, "Other Group Assignees"

    Set mainWs = wb.Worksheets.Add(After:=wb.Worksheets(wb.Worksheets.Count))
    mainWs.Name = "ITS OOSLA INCs"

    Set nwgWs = wb.Worksheets.Add(After:=wb.Worksheets(wb.Worksheets.Count))
    nwgWs.Name = "NWG & CT INCs"

    Set otherWs = wb.Worksheets.Add(After:=wb.Worksheets(wb.Worksheets.Count))
    otherWs.Name = "Other Group Assignees"

    ' Copy raw values.
    src.UsedRange.Copy
    mainWs.Range("A1").PasteSpecial xlPasteValues
    Application.CutCopyMode = False

    ' Delete Type column.
    If LCase$(Trim$(CStr(mainWs.Cells(1, 2).Value))) = "type" Then
        mainWs.Columns(2).Delete
    End If

    ' Add Number as first column.
    mainWs.Columns(1).Insert Shift:=xlToRight

    hdr = Array("Number", "Ticket", "Summary", "Group Assignee", "Status", "P", _
                "Created", "Vendor", "Age of Ticket", "Reassignment Count", _
                "SD Watcher", "Escalation Level", "Escalation Contact Point", _
                "Incident ETR", "Time to resolution", "Reason of OOSLA", _
                "Escalation Time", "OOSLA History", "OOSLA Last Update")

    For c = 0 To UBound(hdr)
        mainWs.Cells(1, c + 1).Value = hdr(c)
    Next c

    lastRow = mainWs.Cells(mainWs.Rows.Count, 2).End(xlUp).Row

    ' Main sheet: 1..all tickets.
    For r = 2 To lastRow
        mainWs.Cells(r, 1).Value = r - 1

        If Len(Trim$(CStr(mainWs.Cells(r, 9).Value))) = 0 Then mainWs.Cells(r, 9).Value = 0
        If Len(Trim$(CStr(mainWs.Cells(r, 10).Value))) = 0 Then mainWs.Cells(r, 10).Value = 0
        If Len(Trim$(CStr(mainWs.Cells(r, 14).Value))) = 0 Then
            mainWs.Cells(r, 14).Value = "N/A"
        Else
            ' Incident ETR can arrive either as an Excel date serial or as date text.
            ' Convert recognizable date text to a real Excel date, then format it.
            If Not IsNumeric(mainWs.Cells(r, 14).Value) Then
                If IsDate(mainWs.Cells(r, 14).Value) Then
                    mainWs.Cells(r, 14).Value = CDate(mainWs.Cells(r, 14).Value)
                End If
            End If
            mainWs.Cells(r, 14).NumberFormat = "m/d/yyyy h:mm"
        End If

        mainWs.Cells(r, 9).NumberFormat = "0"
        mainWs.Cells(r, 10).NumberFormat = "0"

        ' Date/time columns.
        mainWs.Cells(r, 7).NumberFormat = "m/d/yyyy h:mm"
        mainWs.Cells(r, 17).NumberFormat = "m/d/yyyy h:mm"
        mainWs.Cells(r, 19).NumberFormat = "m/d/yyyy h:mm"

        status = Trim$(CStr(mainWs.Cells(r, 5).Value))
        Select Case status
            Case "Assigned to Team"
                mainWs.Cells(r, 5).Interior.Color = RGB(183, 183, 183)
            Case "Pending Cancellation", "Pending Change Implementation", "Pending CHG IMPT"
                mainWs.Cells(r, 5).Interior.Color = RGB(0, 176, 80)
            Case "Pending Customer Action"
                mainWs.Cells(r, 5).Interior.Color = RGB(255, 255, 0)
            Case "In Progress"
                mainWs.Cells(r, 5).Interior.Color = RGB(244, 177, 131)
            Case Else
                mainWs.Cells(r, 5).Interior.Pattern = xlNone
        End Select
    Next r

    ' Delete all tickets with Age of Ticket < 4.
    ' 1, 2, and 3 are deleted; 4 and above are kept.
    For r = lastRow To 2 Step -1
        If IsNumeric(mainWs.Cells(r, 9).Value) Then
            If CDbl(mainWs.Cells(r, 9).Value) < 4 Then
                mainWs.Rows(r).Delete
            End If
        ElseIf Len(Trim$(CStr(mainWs.Cells(r, 9).Value))) = 0 Then
            ' Blank Age values were normalized to 0 above, so this is only
            ' a defensive safeguard.
            mainWs.Rows(r).Delete
        End If
    Next r

    ' Recalculate and regenerate independent numbering after filtering.
    lastRow = mainWs.Cells(mainWs.Rows.Count, 2).End(xlUp).Row
    For r = 2 To lastRow
        mainWs.Cells(r, 1).Value = r - 1
    Next r

    FormatOutputSheet mainWs

    ' Copy headers only to split sheets.
    mainWs.Range("A1:S1").Copy
    nwgWs.Range("A1").PasteSpecial xlPasteValues
    otherWs.Range("A1").PasteSpecial xlPasteValues
    Application.CutCopyMode = False

    nwgRow = 2
    otherRow = 2

    For r = 2 To lastRow
        grp = Trim$(CStr(mainWs.Cells(r, 4).Value))

        If UCase$(Left$(grp, 2)) = "CT" Or UCase$(Left$(grp, 3)) = "NWG" _
           Or UCase$(grp) = "IP OPERATIONS" Then

            ' Copy B:S only; split-sheet Number is generated independently.
            mainWs.Range("B" & r & ":S" & r).Copy
            nwgWs.Range("B" & nwgRow).PasteSpecial xlPasteValues
            nwgRow = nwgRow + 1

        ElseIf Not IsExcludedOtherGroup(grp) Then

            mainWs.Range("B" & r & ":S" & r).Copy
            otherWs.Range("B" & otherRow).PasteSpecial xlPasteValues
            otherRow = otherRow + 1

        End If
    Next r

    Application.CutCopyMode = False

    ' Independent numbering for each split sheet.
    For r = 2 To nwgRow - 1
        nwgWs.Cells(r, 1).Value = r - 1
    Next r

    For r = 2 To otherRow - 1
        otherWs.Cells(r, 1).Value = r - 1
    Next r

    ' In split sheets ONLY, remove:
    ' - Time to resolution
    ' - OOSLA History
    '
    ' Current positions are O (15) and R (18).
    ' Delete rightmost first.
    nwgWs.Columns(18).Delete
    nwgWs.Columns(15).Delete

    otherWs.Columns(18).Delete
    otherWs.Columns(15).Delete

    NormalizeAndFormatSplitSheet nwgWs
    NormalizeAndFormatSplitSheet otherWs

    mainWs.Move Before:=wb.Worksheets(1)
    nwgWs.Move After:=mainWs
    otherWs.Move After:=nwgWs

    mainWs.Activate

CleanExit:
    Application.DisplayAlerts = True
    Application.EnableEvents = True
    Application.ScreenUpdating = True
    Exit Sub

CleanFail:
    MsgBox "OOSLA report generation failed: " & Err.Description, vbCritical
    Resume CleanExit

End Sub


Private Function IsExcludedOtherGroup(ByVal grp As String) As Boolean
    Dim g As String

    ' Normalize case, non-breaking spaces, and common dash variants so that
    ' Architecture Group – ESB is excluded even if Excel contains a different
    ' Unicode dash/space representation.
    g = LCase$(Trim$(grp))
    g = Replace(g, ChrW(&HA0), " ")
    g = Replace(g, ChrW(&H2013), "-") ' en dash
    g = Replace(g, ChrW(&H2014), "-") ' em dash
    g = Replace(g, ChrW(&H2011), "-") ' non-breaking hyphen
    g = Replace(g, ChrW(&H2212), "-") ' minus sign

    Do While InStr(g, "  ") > 0
        g = Replace(g, "  ", " ")
    Loop

    IsExcludedOtherGroup = _
        (g = "tecnotree l3") Or _
        (g = "its tecnotree l3 support") Or _
        (g = "architecture group - esb")
End Function


Private Sub NormalizeAndFormatSplitSheet(ByVal ws As Worksheet)

    Dim lr As Long, r As Long, s As String

    lr = ws.Cells(ws.Rows.Count, 2).End(xlUp).Row
    If lr < 1 Then Exit Sub

    For r = 2 To lr

        If Len(Trim$(CStr(ws.Cells(r, 9).Value))) = 0 Then ws.Cells(r, 9).Value = 0
        If Len(Trim$(CStr(ws.Cells(r, 10).Value))) = 0 Then ws.Cells(r, 10).Value = 0
        If Len(Trim$(CStr(ws.Cells(r, 14).Value))) = 0 Then
            ws.Cells(r, 14).Value = "N/A"
        Else
            If Not IsNumeric(ws.Cells(r, 14).Value) Then
                If IsDate(ws.Cells(r, 14).Value) Then
                    ws.Cells(r, 14).Value = CDate(ws.Cells(r, 14).Value)
                End If
            End If
            ws.Cells(r, 14).NumberFormat = "m/d/yyyy h:mm"
        End If

        ws.Cells(r, 9).NumberFormat = "0"
        ws.Cells(r, 10).NumberFormat = "0"

        ' After deleting O and R:
        ' G = Created, P = Escalation Time, R = OOSLA Last Update.
        ws.Cells(r, 7).NumberFormat = "m/d/yyyy h:mm"
        ws.Cells(r, 16).NumberFormat = "m/d/yyyy h:mm"
        ws.Cells(r, 18).NumberFormat = "m/d/yyyy h:mm"

        s = Trim$(CStr(ws.Cells(r, 5).Value))
        Select Case s
            Case "Assigned to Team"
                ws.Cells(r, 5).Interior.Color = RGB(183, 183, 183)
            Case "Pending Cancellation", "Pending Change Implementation", "Pending CHG IMPT"
                ws.Cells(r, 5).Interior.Color = RGB(0, 176, 80)
            Case "Pending Customer Action"
                ws.Cells(r, 5).Interior.Color = RGB(255, 255, 0)
            Case "In Progress"
                ws.Cells(r, 5).Interior.Color = RGB(244, 177, 131)
        End Select
    Next r

    FormatOutputSheet ws

End Sub

Private Sub FormatOutputSheet(ByVal ws As Worksheet)

    Dim lr As Long, lc As Long

    lr = ws.Cells(ws.Rows.Count, 2).End(xlUp).Row
    lc = ws.Cells(1, ws.Columns.Count).End(xlToLeft).Column
    If lr < 1 Then Exit Sub

    With ws.Range(ws.Cells(1, 1), ws.Cells(lr, lc))
        .HorizontalAlignment = xlCenter
        .VerticalAlignment = xlCenter
        .WrapText = False
        .Borders.LineStyle = xlContinuous
        .Borders.Weight = xlThin
    End With

    With ws.Range(ws.Cells(1, 1), ws.Cells(1, lc))
        .Interior.Color = RGB(0, 176, 240)
        .Font.Bold = True
        .Font.Name = "Calibri"
        .Font.Size = 11
    End With

    ' Final date/time safeguard for Incident ETR.
    If lr >= 2 Then
        ws.Range("N2:N" & lr).NumberFormat = "m/d/yyyy h:mm"
    End If

    ws.Rows(1).RowHeight = 30

    ' REQUIRED AUTOFIT SEQUENCE:
    ' 1. Remove Wrap Text from the whole table.
    With ws.Range(ws.Cells(1, 1), ws.Cells(lr, lc))
        .WrapText = False
    End With

    ' 2. AutoFit column widths while Wrap Text is OFF.
    ws.Columns.AutoFit

    ' 3. Re-enable Wrap Text for the whole table.
    With ws.Range(ws.Cells(1, 1), ws.Cells(lr, lc))
        .WrapText = True
    End With

    ' 4. AutoFit row heights after Wrap Text is restored.
    ws.Rows("1:" & lr).AutoFit

    ws.Range(ws.Cells(1, 1), ws.Cells(lr, lc)).AutoFilter
    ws.Activate
    ActiveWindow.FreezePanes = False
    ws.Range("A2").Select
    ActiveWindow.FreezePanes = True

End Sub

Private Sub DeleteSheetIfExists(ByVal wb As Workbook, ByVal sheetName As String)
    On Error Resume Next
    wb.Worksheets(sheetName).Delete
    On Error GoTo 0
End Sub
