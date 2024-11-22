import flet as ft


def main(page: ft.Page):
    page.title = "Hello!!"
    page.add(ft.SafeArea(ft.Text("Hello, Flet!")))

    page.add(ft.FilledButton("Click me!"))
ft.app(main)
