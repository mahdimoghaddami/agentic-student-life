#import "@preview/touying:0.8.0": config-page, themes
#import themes.simple: simple-theme, slide

#let olive = rgb("646f3c")
#let cream = rgb("fffbe7")
#let orange = rgb("b05024")
#let ink = rgb("#000000")
#let ink2 = rgb("25291d")
#let slide-margin = 32pt
#let page-number-size = 8pt
#let page-number-fill = orange
#let heading-font = "Libertinus Serif"
#let body-font = "Libertinus Sans"
#let body-font-size = 15pt
#let math-font = "New Computer Modern Math"
#let math-font-size = 16pt
#let mono-font = "Libertinus Mono"
#let mono-font-size = 14pt
#let title-font-size = 32pt
#let section-font-size = 72pt

#let apply-theme(entire-document, text-size: body-font-size, math-size: math-font-size) = {
  set text(font: body-font, size: text-size, fill: ink)
  show math.equation: set text(font: math-font, size: math-size)
  entire-document
}

#let slide-title(title-string, color: olive, font-size: title-font-size, venue: none) = {
  // text(font: "Libertinus Serif", size: 38pt, fill: olive, title-string)
  heading(level: 2)[#text(font: heading-font, weight: "bold", size: font-size, fill: color, title-string) #text(
      font: heading-font,
      weight: "regular",
      size: body-font-size,
      fill: color,
      venue,
    )]
}

#let section-slide(section-title-string, color: cream, font-size: section-font-size) = {
  set par(leading: 0.4em)
  slide(config: config-page(fill: orange, footer: none))[#align(horizon, heading()[#text(
    font: heading-font,
    weight: "regular",
    size: font-size,
    fill: color,
    section-title-string,
  )])]
}

#let split-slide(
  left_percentage,
  left-body,
  right-body,
  left-color-bg: olive,
  right-color-bg: cream,
  left-color-txt: cream,
  right-color-txt: ink,
) = slide(
  config: config-page(margin: 0pt, footer: context place(bottom + right, dx: -slide-margin, dy: -20pt)[#text(
    size: page-number-size,
    fill: page-number-fill,
  )[#counter(page).display() / #counter(page).final().first()]]),
)[
  #grid(
    columns: (left_percentage, auto),
    block(
      width: 100%,
      height: 100%,
      fill: left-color-bg,
      inset: slide-margin,
    )[
      #set text(fill: left-color-txt)
      #left-body
    ],
    block(
      width: 100%,
      height: 100%,
      fill: cream,
      inset: slide-margin,
    )[
      #set text(fill: right-color-txt)
      #right-body
    ],
  )
]
