"use client"

import EmojiPicker, { EmojiStyle, SuggestionMode, type EmojiClickData } from "emoji-picker-react"
import { SmileIcon } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"

interface RichTextEditorEmojiPopoverProps {
    open: boolean
    onOpenChange: (open: boolean) => void
    onSelectEmoji: (emoji: string) => void
}

export function RichTextEditorEmojiPopover({
    open,
    onOpenChange,
    onSelectEmoji,
}: RichTextEditorEmojiPopoverProps) {
    const [suggestedEmojisMode, setSuggestedEmojisMode] = useState<SuggestionMode>(SuggestionMode.FREQUENT)

    const handleOpenChange = (nextOpen: boolean) => {
        if (nextOpen) {
            setSuggestedEmojisMode(SuggestionMode.FREQUENT)
        }
        onOpenChange(nextOpen)
    }

    const handleEmojiClick = (emojiData: EmojiClickData) => {
        onSelectEmoji(emojiData.emoji)
    }

    return (
        <Popover open={open} onOpenChange={handleOpenChange}>
            <PopoverTrigger
                render={
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="size-8 p-0"
                        aria-label="Insert Emoji"
                    >
                        <SmileIcon className="size-4" />
                    </Button>
                }
            />
            <PopoverContent className="w-[27rem] p-2" align="start">
                <div className="space-y-2">
                    <div className="flex items-center justify-between px-1">
                        <span className="text-xs font-medium text-muted-foreground">Suggested</span>
                        <div className="flex items-center gap-1">
                            <Button
                                type="button"
                                variant={suggestedEmojisMode === SuggestionMode.FREQUENT ? "default" : "ghost"}
                                size="sm"
                                className="h-7 px-2 text-xs"
                                onClick={() => setSuggestedEmojisMode(SuggestionMode.FREQUENT)}
                            >
                                Frequent
                            </Button>
                            <Button
                                type="button"
                                variant={suggestedEmojisMode === SuggestionMode.RECENT ? "default" : "ghost"}
                                size="sm"
                                className="h-7 px-2 text-xs"
                                onClick={() => setSuggestedEmojisMode(SuggestionMode.RECENT)}
                            >
                                Recent
                            </Button>
                        </div>
                    </div>

                    <div data-testid="emoji-picker-root" className="[&_aside.EmojiPickerReact]:!w-full">
                        <EmojiPicker
                            onEmojiClick={handleEmojiClick}
                            suggestedEmojisMode={suggestedEmojisMode}
                            emojiStyle={EmojiStyle.NATIVE}
                            searchPlaceholder="Search emojis"
                            lazyLoadEmojis
                            width="100%"
                            height={360}
                            previewConfig={{ showPreview: false }}
                        />
                    </div>
                </div>
            </PopoverContent>
        </Popover>
    )
}
