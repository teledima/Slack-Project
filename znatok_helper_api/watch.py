from slack_core.sheets import find_rows, authorize


def start_watch(link, channel, ts, status=None):
    sheet = authorize().open('Кандидаты(версия 2)').worksheet('watched_tasks')
    row_cells = find_rows(sheet, [link, channel, ts])

    if len(row_cells) >= 1:
        if len(row_cells) > 1:
            sheet.delete_row(row_cells.pop().row)
        [sheet.update_cell(row=cell.row, col=4, value=status)
         for cell in sheet.findall(query=link, in_column=1) if status is not None]
    else:
        sheet.append_row([link, channel, ts, status])
    return True


def end_watch(link, channel=None, ts=None):
    sheet = authorize().open('Кандидаты(версия 2)').worksheet('watched_tasks')
    row_values = [link]
    if channel:
        row_values.append(channel)
    if ts:
        row_values.append(ts)
    rows = [row_cells[0].row for row_cells in find_rows(sheet, row_values=row_values) if len(row_cells) > 0]
    rows.sort(reverse=True)
    [sheet.delete_row(row) for row in rows]
    return len(rows)
