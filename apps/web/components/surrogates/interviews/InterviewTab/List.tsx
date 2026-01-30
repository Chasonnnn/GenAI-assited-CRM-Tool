"use client"

import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardTitle } from "@/components/ui/card"
import { PlusIcon } from "lucide-react"
import { useInterviewTab } from "./context"
import { ListItem } from "./ListItem"

interface ListProps {
    className?: string | undefined
}

export function List({ className }: ListProps) {
    const { interviews, selectedId, selectInterview, openEditor, canEdit } = useInterviewTab()

    return (
        <Card className={className}>
            <CardHeader className="flex flex-row items-center justify-between py-3 px-4 border-b shrink-0">
                <CardTitle className="text-base">Interviews ({interviews.length})</CardTitle>
                {canEdit && (
                    <Button size="sm" onClick={() => openEditor()}>
                        <PlusIcon className="h-4 w-4" />
                    </Button>
                )}
            </CardHeader>
            <div className="flex-1 overflow-auto">
                {interviews.map((interview) => (
                    <ListItem
                        key={interview.id}
                        interview={interview}
                        isSelected={selectedId === interview.id}
                        onClick={() => selectInterview(interview.id)}
                    />
                ))}
            </div>
        </Card>
    )
}
