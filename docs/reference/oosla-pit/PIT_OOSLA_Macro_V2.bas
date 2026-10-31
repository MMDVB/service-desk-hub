Attribute VB_Name = "PIT_OOSLA_Macro"
Option Explicit

'==========================================================
' PIT OOSLA INCs - Daily Report Generator V2
' Based on:
'   - PIT_OOSLA_Macro_Master_Prompt_for_AI.txt
'   - OOSLA PIT (4).xlsx raw structure
'   - "PIT OOSLA INCs" reference output structure
'
' Important:
' - The macro works against the ACTIVE worksheet as the raw source.
' - It creates/recreates "PIT OOSLA INCs".
' - Source data is copied as values.
' - The output contains exactly 12 columns in the required order.
'==========================================================

Private Const OUTPUT_SHEET_NAME As String = "PIT OOSLA INCs"

Public Sub GenerateDailyReport()
    Dim wb As Workbook
    Dim srcWs As Worksheet
    Dim outWs As Worksheet

    Dim oldScreenUpdating As Boolean
    Dim oldEnableEvents As Boolean
    Dim oldDisplayAlerts As Boolean

    On Error GoTo CleanFail

    Set wb = ActiveWorkbook
    Set srcWs = ActiveSheet

    If wb Is Nothing Then Err.Raise vbObjectError + 1000, , "No active workbook is available."
    If srcWs Is Nothing Then Err.Raise vbObjectError + 1001, , "No active source worksheet is available."

    ' Store Excel application settings so they can always be restored.
    oldScreenUpdating = Application.ScreenUpdating
    oldEnableEvents = Application.EnableEvents
    oldDisplayAlerts = Application.DisplayAlerts

    Application.ScreenUpdating = False
    Application.EnableEvents = False
    Application.DisplayAlerts = False

    ' Rebuild the generated output every run.
    DeleteSheetIfExists wb, OUTPUT_SHEET_NAME

    Set outWs = wb.Worksheets.Add(After:=wb.Worksheets(wb.Worksheets.Count))
    outWs.Name = OUTPUT_SHEET_NAME

    BuildMainReport srcWs, outWs
    FormatOutputSheet outWs
    FreezeHeaderRow outWs

CleanExit:
    Application.ScreenUpdating = oldScreenUpdating
    Application.EnableEvents = oldEnableEvents
    Application.DisplayAlerts = oldDisplayAlerts

    If Err.Number = 0 Then
        outWs.Activate
        MsgBox "PIT OOSLA INCs report generated successfully." & vbCrLf & _
               "Tickets processed: " & GetTicketCount(outWs), _
               vbInformation, "PIT OOSLA Report"
    End If
    Exit Sub

CleanFail:
    Dim errMsg As String
    errMsg = "PIT OOSLA report generation failed." & vbCrLf & vbCrLf & _
             "Error " & Err.Number & ": " & Err.Description

    Application.ScreenUpdating = oldScreenUpdating
    Application.EnableEvents = oldEnableEvents
    Application.DisplayAlerts = oldDisplayAlerts

    MsgBox errMsg, vbCritical, "PIT OOSLA Report"
End Sub

Private Sub BuildMainReport(ByVal srcWs As Worksheet, ByVal outWs As Worksheet)
    Dim lastSrcRow As Long
    Dim lastSrcCol As Long
    Dim dataLastRow As Long
    Dim srcHeaders As Object
    Dim requiredHeaders As Variant
    Dim sourceHeaderNames As Variant

    Dim r As Long
    Dim outRow As Long
    Dim i As Long
    Dim sourceCol As Long
    Dim headerName As String
    Dim ticketValue As String

    requiredHeaders = Array( _
        "Number", _
        "Ticket", _
        "Summary", _
        "PIT", _
        "Group Assignee", _
        "P", _
        "Status", _
        "Created", _
        "Updated", _
        "Age of Ticket", _
        "Vendor", _
        "Project Picker")

    sourceHeaderNames = Array( _
        "Ticket#", _
        "Summary", _
        "PIT", _
        "Group Assignee", _
        "P", _
        "Status", _
        "Created", _
        "Updated", _
        "Age of Ticket", _
        "Vendor", _
        "Project Picker")

    lastSrcRow = GetLastUsedRow(srcWs)
    lastSrcCol = GetLastUsedColumn(srcWs)

    If lastSrcRow < 2 Then
        Err.Raise vbObjectError + 1100, , _
                  "The active source worksheet does not contain any ticket data."
    End If

    Set srcHeaders = BuildHeaderMap(srcWs, lastSrcCol)

    ' Validate required source fields.
    For i = LBound(sourceHeaderNames) To UBound(sourceHeaderNames)
        headerName = CStr(sourceHeaderNames(i))
        If Not srcHeaders.Exists(NormalizeHeader(headerName)) Then
            Err.Raise vbObjectError + 1102, , _
                      "Required source column not found: " & headerName
        End If
    Next i

    '==========================================================
    ' V2 - FIND THE REAL DATA LAST ROW
    '
    ' The raw export contains a final formula row such as:
    '     =COUNTA(B2:B45)
    '
    ' That row is NOT a ticket and must never enter the report.
    ' We explicitly detect it BEFORE copying any data.
    '==========================================================
    dataLastRow = FindLastTicketRow(srcWs, _
                                    CLng(srcHeaders(NormalizeHeader("Ticket#"))), _
                                    lastSrcRow)

    If dataLastRow < 2 Then
        Err.Raise vbObjectError + 1103, , _
                  "No valid ticket rows were found after removing the raw export footer/formula row."
    End If

    ' Final headers.
    For i = LBound(requiredHeaders) To UBound(requiredHeaders)
        outWs.Cells(1, i + 1).Value = requiredHeaders(i)
    Next i

    '==========================================================
    ' COPY ONLY REAL TICKET ROWS
    '==========================================================
    outRow = 2

    For r = 2 To dataLastRow
        ' Extra safety: do not copy blank ticket rows or COUNTA footer rows.
        ticketValue = Trim$(CStr(srcWs.Cells(r, _
                              CLng(srcHeaders(NormalizeHeader("Ticket#")))).Value))

        If Len(ticketValue) > 0 And Not IsCountAFormulaRow(srcWs, r) Then

            ' Number is temporary here.
            outWs.Cells(outRow, 1).Value = outRow - 1

            For i = LBound(sourceHeaderNames) To UBound(sourceHeaderNames)
                headerName = CStr(sourceHeaderNames(i))
                sourceCol = CLng(srcHeaders(NormalizeHeader(headerName)))

                ' Copy VALUE only.
                outWs.Cells(outRow, i + 2).Value = srcWs.Cells(r, sourceCol).Value
            Next i

            outRow = outRow + 1
        End If
    Next r

    '==========================================================
    ' V2 - SORT BY AGE OF TICKET, BIGGEST TO SMALLEST
    '
    ' Age of Ticket is output column J.
    ' Sort the COMPLETE report rows, not only column J.
    ' This keeps every ticket's fields together.
    '==========================================================
    If outRow > 2 Then
        SortReportByAge outWs, outRow - 1

        ' Regenerate Number 1..N AFTER sorting.
        RenumberReport outWs, outRow - 1
    End If
End Sub

Private Function FindLastTicketRow(ByVal ws As Worksheet, _
                                   ByVal ticketCol As Long, _
                                   ByVal lastUsedRow As Long) As Long
    Dim r As Long
    Dim valueText As String

    ' Start from the bottom and locate the last genuine ticket row.
    For r = lastUsedRow To 2 Step -1
        valueText = Trim$(CStr(ws.Cells(r, ticketCol).Value))

        If Len(valueText) > 0 Then
            If Not IsCountAFormulaRow(ws, r) Then
                FindLastTicketRow = r
                Exit Function
            End If
        End If
    Next r

    FindLastTicketRow = 1
End Function

Private Function IsCountAFormulaRow(ByVal ws As Worksheet, ByVal rowNumber As Long) As Boolean
    Dim c As Long
    Dim lastCol As Long
    Dim cellText As String

    ' Detect the raw export footer robustly.
    ' Today's example contains =COUNTA(B2:B45).
    lastCol = GetLastUsedColumn(ws)

    For c = 1 To lastCol
        If ws.Cells(rowNumber, c).HasFormula Then
            cellText = UCase$(Replace(CStr(ws.Cells(rowNumber, c).Formula), " ", ""))

            If Left$(cellText, 8) = "=COUNTA(" Then
                IsCountAFormulaRow = True
                Exit Function
            End If
        End If
    Next c

    IsCountAFormulaRow = False
End Function

Private Sub SortReportByAge(ByVal ws As Worksheet, ByVal lastDataRow As Long)
    Dim sortRange As Range

    If lastDataRow < 3 Then Exit Sub

    Set sortRange = ws.Range(ws.Cells(1, 1), ws.Cells(lastDataRow, 12))

    ' Age of Ticket = column J.
    ' The raw values are converted to numeric values before sorting.
    NormalizeAgeColumn ws, 2, lastDataRow

    With ws.Sort
        .SortFields.Clear

        .SortFields.Add Key:=ws.Range("J2:J" & lastDataRow), _
                        SortOn:=xlSortOnValues, _
                        Order:=xlDescending, _
                        DataOption:=xlSortNormal

        .SetRange sortRange
        .Header = xlYes
        .MatchCase = False
        .Orientation = xlTopToBottom
        .Apply
    End With
End Sub

Private Sub NormalizeAgeColumn(ByVal ws As Worksheet, _
                               ByVal firstRow As Long, _
                               ByVal lastRow As Long)
    Dim r As Long
    Dim rawValue As Variant
    Dim numericAge As Double

    For r = firstRow To lastRow
        rawValue = ws.Cells(r, 10).Value ' Age of Ticket = J

        If IsNumeric(rawValue) Then
            ws.Cells(r, 10).Value = CDbl(rawValue)
        Else
            numericAge = ExtractLeadingNumber(CStr(rawValue))
            If numericAge >= 0 Then
                ws.Cells(r, 10).Value = numericAge
            End If
        End If
    Next r
End Sub

Private Function ExtractLeadingNumber(ByVal valueText As String) As Double
    Dim s As String
    Dim i As Long
    Dim ch As String
    Dim result As String
    Dim decimalFound As Boolean

    s = Trim$(valueText)
    result = ""
    decimalFound = False

    For i = 1 To Len(s)
        ch = Mid$(s, i, 1)

        If ch >= "0" And ch <= "9" Then
            result = result & ch
        ElseIf ch = "." And Not decimalFound Then
            result = result & ch
            decimalFound = True
        ElseIf Len(result) > 0 Then
            Exit For
        End If
    Next i

    If Len(result) > 0 And IsNumeric(result) Then
        ExtractLeadingNumber = CDbl(result)
    Else
        ExtractLeadingNumber = -1
    End If
End Function

Private Sub RenumberReport(ByVal ws As Worksheet, ByVal lastDataRow As Long)
    Dim r As Long

    If lastDataRow < 2 Then Exit Sub

    For r = 2 To lastDataRow
        ws.Cells(r, 1).Value = r - 1
    Next r
End Sub

Private Sub FormatOutputSheet(ByVal ws As Worksheet)
    Dim lastRow As Long
    Dim lastCol As Long
    Dim usedRange As Range
    Dim headerRange As Range

    lastRow = GetLastUsedRow(ws)
    lastCol = GetLastUsedColumn(ws)

    If lastRow < 1 Or lastCol < 1 Then Exit Sub

    Set usedRange = ws.Range(ws.Cells(1, 1), ws.Cells(lastRow, lastCol))
    Set headerRange = ws.Range(ws.Cells(1, 1), ws.Cells(1, lastCol))

    ' General font.
    With usedRange.Font
        .Name = "Calibri"
        .Size = 11
    End With

    ' Borders on every used cell.
    With usedRange.Borders
        .LineStyle = xlContinuous
        .Weight = xlThin
    End With

    ' Center everything horizontally and vertically.
    With usedRange
        .HorizontalAlignment = xlCenter
        .VerticalAlignment = xlCenter
    End With

    ' Header formatting.
    With headerRange
        .Interior.Color = RGB(0, 176, 240)
        .Font.Bold = True
        .HorizontalAlignment = xlCenter
        .VerticalAlignment = xlCenter
        .WrapText = True
    End With

    ' Explicit date/time number formats.
    ws.Columns(8).NumberFormat = "m/d/yyyy h:mm"   ' Created
    ws.Columns(9).NumberFormat = "m/d/yyyy h:mm"   ' Updated

    ' Hide gridlines where possible.
    ws.Activate
    ActiveWindow.DisplayGridlines = False

    ' Status colors.
    ColorStatuses ws

    '------------------------------------------------------
    ' REQUIRED AUTOFIT SEQUENCE
    ' 1) Wrap OFF
    ' 2) AutoFit Columns
    ' 3) Wrap ON
    ' 4) AutoFit Rows
    '------------------------------------------------------
    usedRange.WrapText = False
    usedRange.Columns.AutoFit

    usedRange.WrapText = True
    usedRange.Rows.AutoFit

    ' Re-apply date formats after formatting to ensure they are preserved.
    ws.Columns(8).NumberFormat = "m/d/yyyy h:mm"
    ws.Columns(9).NumberFormat = "m/d/yyyy h:mm"

    ' Keep header visually distinct after the final formatting pass.
    headerRange.Font.Bold = True
    headerRange.WrapText = True
End Sub

Private Sub ColorStatuses(ByVal ws As Worksheet)
    Dim lastRow As Long
    Dim r As Long
    Dim statusText As String

    lastRow = GetLastUsedRow(ws)
    If lastRow < 2 Then Exit Sub

    For r = 2 To lastRow
        statusText = LCase$(Trim$(CStr(ws.Cells(r, 7).Value))) ' Status is column G.

        ' Clear previous status fill first.
        ws.Cells(r, 7).Interior.Pattern = xlNone

        Select Case statusText
            Case "assigned to team"
                ws.Cells(r, 7).Interior.Color = RGB(183, 183, 183)

            Case "pending cancellation"
                ws.Cells(r, 7).Interior.Color = RGB(0, 176, 80)

            Case "pending change implementation"
                ws.Cells(r, 7).Interior.Color = RGB(0, 176, 80)

            Case "pending customer action"
                ws.Cells(r, 7).Interior.Color = RGB(255, 255, 0)

            Case "in progress"
                ws.Cells(r, 7).Interior.Color = RGB(244, 177, 131)
        End Select
    Next r
End Sub

Private Function BuildHeaderMap(ByVal ws As Worksheet, ByVal lastCol As Long) As Object
    Dim dict As Object
    Dim c As Long
    Dim headerText As String
    Dim key As String

    Set dict = CreateObject("Scripting.Dictionary")
    dict.CompareMode = vbTextCompare

    For c = 1 To lastCol
        headerText = CStr(ws.Cells(1, c).Value)
        key = NormalizeHeader(headerText)

        If Len(key) > 0 Then
            ' If duplicate headers exist, keep the first occurrence.
            ' The PIT output fields do not rely on the removable duplicate
            ' "Resolution" columns.
            If Not dict.Exists(key) Then
                dict.Add key, c
            End If
        End If
    Next c

    Set BuildHeaderMap = dict
End Function

Private Function NormalizeHeader(ByVal headerText As String) As String
    Dim s As String

    s = CStr(headerText)
    s = Replace(s, ChrW(160), " ")
    s = Application.WorksheetFunction.Trim(s)
    NormalizeHeader = LCase$(s)
End Function

Private Sub FreezeHeaderRow(ByVal ws As Worksheet)
    ws.Activate
    ActiveWindow.FreezePanes = False
    ws.Range("A2").Select
    ActiveWindow.FreezePanes = True
End Sub

Private Sub DeleteSheetIfExists(ByVal wb As Workbook, ByVal sheetName As String)
    Dim ws As Worksheet

    On Error Resume Next
    Set ws = wb.Worksheets(sheetName)
    On Error GoTo 0

    If Not ws Is Nothing Then
        ws.Delete
    End If
End Sub

Private Function GetLastUsedRow(ByVal ws As Worksheet) As Long
    Dim lastCell As Range

    On Error Resume Next
    Set lastCell = ws.Cells.Find(What:="*", _
                                 After:=ws.Cells(1, 1), _
                                 LookAt:=xlPart, _
                                 LookIn:=xlFormulas, _
                                 SearchOrder:=xlByRows, _
                                 SearchDirection:=xlPrevious, _
                                 MatchCase:=False)
    On Error GoTo 0

    If lastCell Is Nothing Then
        GetLastUsedRow = 0
    Else
        GetLastUsedRow = lastCell.Row
    End If
End Function

Private Function GetLastUsedColumn(ByVal ws As Worksheet) As Long
    Dim lastCell As Range

    On Error Resume Next
    Set lastCell = ws.Cells.Find(What:="*", _
                                 After:=ws.Cells(1, 1), _
                                 LookAt:=xlPart, _
                                 LookIn:=xlFormulas, _
                                 SearchOrder:=xlByColumns, _
                                 SearchDirection:=xlPrevious, _
                                 MatchCase:=False)
    On Error GoTo 0

    If lastCell Is Nothing Then
        GetLastUsedColumn = 0
    Else
        GetLastUsedColumn = lastCell.Column
    End If
End Function

Private Function GetTicketCount(ByVal ws As Worksheet) As Long
    Dim lastRow As Long

    lastRow = GetLastUsedRow(ws)

    If lastRow <= 1 Then
        GetTicketCount = 0
    Else
        GetTicketCount = lastRow - 1
    End If
End Function
