"use client"

import * as React from "react"
import useEmblaCarousel, {
  type UseEmblaCarouselType,
} from "embla-carousel-react"

import { cn } from '@/lib/utils'

type CarouselApi = UseEmblaCarouselType[1]
type UseCarouselParameters = Parameters<typeof useEmblaCarousel>
type CarouselOptions = UseCarouselParameters[0]
type CarouselPlugin = UseCarouselParameters[1]

type CarouselProps = {
  opts?: CarouselOptions
  plugins?: CarouselPlugin
  orientation?: "horizontal" | "vertical"
  setApi?: (api: CarouselApi) => void
}

function Carousel({
  orientation = "horizontal",
  opts,
  setApi,
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
  const setApiRef = React.useRef(setApi)

  React.useEffect(() => {
    setApiRef.current = setApi
  }, [setApi])

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

  React.useEffect(() => {
    if (!api) return
    setApiRef.current?.(api)
  }, [api])

  React.useEffect(() => {
    if (!api) return
    const handleSelect = () => undefined

    api.on("reInit", handleSelect)
    api.on("select", handleSelect)

    return () => {
      api.off("reInit", handleSelect)
      api.off("select", handleSelect)
    }
  }, [api])

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
