"use client"

import * as React from "react"
import useEmblaCarousel from "embla-carousel-react"

import { cn } from '@/lib/utils'

type UseCarouselParameters = Parameters<typeof useEmblaCarousel>
type CarouselOptions = UseCarouselParameters[0]
type CarouselPlugin = UseCarouselParameters[1]

type CarouselProps = {
  opts?: CarouselOptions
  plugins?: CarouselPlugin
  orientation?: "horizontal" | "vertical"
}

function Carousel({
  orientation = "horizontal",
  opts,
  plugins,
  className,
  children,
  "aria-label": ariaLabel,
  "aria-labelledby": ariaLabelledBy,
  ...props
}: React.ComponentProps<"section"> & CarouselProps) {
  const [, api] = useEmblaCarousel(
    {
      ...opts,
      axis: orientation === "horizontal" ? "x" : "y",
    },
    plugins
  )

  const scrollPrev = () => {
    api?.scrollPrev()
  }

  const scrollNext = () => {
    api?.scrollNext()
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLElement>) => {
    if (event.key === "ArrowLeft") {
      event.preventDefault()
      scrollPrev()
    } else if (event.key === "ArrowRight") {
      event.preventDefault()
      scrollNext()
    }
  }

  return (
    <section
      onKeyDownCapture={handleKeyDown}
      className={cn("relative", className)}
      aria-label={ariaLabel ?? (ariaLabelledBy ? undefined : "Carousel")}
      aria-labelledby={ariaLabelledBy}
      aria-roledescription="carousel"
      data-slot="carousel"
      {...props}
    >
      {children}
    </section>
  )
}

export {
  Carousel,
}
