"use client"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import {
  FolderIcon,
  CheckSquareIcon,
  ClockIcon,
  PlusIcon,
} from "lucide-react"

export default function DashboardPage() {
  return (
    <div className="flex flex-1 flex-col gap-4 p-4 md:p-6">
      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">My Open Cases</CardTitle>
            <FolderIcon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">12</div>
            <p className="text-xs text-muted-foreground">3 new this week</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Tasks Due Today</CardTitle>
            <CheckSquareIcon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">5</div>
            <p className="text-xs text-destructive">2 overdue</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Pending Review</CardTitle>
            <ClockIcon className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">8</div>
            <p className="text-xs text-muted-foreground">Cases awaiting action</p>
          </CardContent>
        </Card>
      </div>

      {/* Tasks & Activity */}
      <div className="grid gap-4 md:grid-cols-[1.6fr_1fr]">
        {/* My Tasks Card */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>My Tasks</CardTitle>
            <Button variant="link" className="h-auto p-0 text-sm">
              View All
            </Button>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-start gap-3">
              <Checkbox id="task-1" className="mt-1" />
              <div className="flex-1 space-y-1">
                <label
                  htmlFor="task-1"
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  Follow up with Case #00042
                </label>
                <div className="flex items-center gap-2">
                  <Badge variant="destructive" className="text-xs">
                    Overdue
                  </Badge>
                  <a href="/cases/00042" className="text-xs text-muted-foreground hover:underline">
                    #00042
                  </a>
                </div>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <Checkbox id="task-2" className="mt-1" />
              <div className="flex-1 space-y-1">
                <label
                  htmlFor="task-2"
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  Review questionnaire for Case #00038
                </label>
                <div className="flex items-center gap-2">
                  <Badge variant="default" className="bg-amber-500 text-xs hover:bg-amber-500/80">
                    Today
                  </Badge>
                  <a href="/cases/00038" className="text-xs text-muted-foreground hover:underline">
                    #00038
                  </a>
                </div>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <Checkbox id="task-3" className="mt-1" />
              <div className="flex-1 space-y-1">
                <label
                  htmlFor="task-3"
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  Schedule consultation for Case #00045
                </label>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="text-xs">
                    Tomorrow
                  </Badge>
                  <a href="/cases/00045" className="text-xs text-muted-foreground hover:underline">
                    #00045
                  </a>
                </div>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <Checkbox id="task-4" className="mt-1" />
              <div className="flex-1 space-y-1">
                <label
                  htmlFor="task-4"
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  Update medical records for Case #00039
                </label>
                <div className="flex items-center gap-2">
                  <Badge variant="destructive" className="text-xs">
                    Overdue
                  </Badge>
                  <a href="/cases/00039" className="text-xs text-muted-foreground hover:underline">
                    #00039
                  </a>
                </div>
              </div>
            </div>

            <div className="flex items-start gap-3">
              <Checkbox id="task-5" className="mt-1" />
              <div className="flex-1 space-y-1">
                <label
                  htmlFor="task-5"
                  className="text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
                >
                  Prepare contract documents for Case #00041
                </label>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary" className="text-xs">
                    Next Week
                  </Badge>
                  <a href="/cases/00041" className="text-xs text-muted-foreground hover:underline">
                    #00041
                  </a>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2 pt-2">
              <Input placeholder="Add a task..." className="flex-1" />
              <Button size="icon" variant="ghost">
                <PlusIcon className="h-4 w-4" />
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Recent Activity Card */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Recent Activity</CardTitle>
            <Button variant="link" className="h-auto p-0 text-sm">
              View All
            </Button>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-3">
              <div className="relative mt-1">
                <div className="h-2 w-2 rounded-full bg-blue-500" />
              </div>
              <div className="flex-1 space-y-1">
                <p className="text-sm">Case #00042 moved to Contacted</p>
                <p className="text-xs text-muted-foreground">2h ago</p>
              </div>
            </div>

            <div className="flex gap-3">
              <div className="relative mt-1">
                <div className="h-2 w-2 rounded-full bg-green-500" />
              </div>
              <div className="flex-1 space-y-1">
                <p className="text-sm">Note added to Case #00038</p>
                <p className="text-xs text-muted-foreground">3h ago</p>
              </div>
            </div>

            <div className="flex gap-3">
              <div className="relative mt-1">
                <div className="h-2 w-2 rounded-full bg-yellow-500" />
              </div>
              <div className="flex-1 space-y-1">
                <p className="text-sm">New case created from Meta</p>
                <p className="text-xs text-muted-foreground">5h ago</p>
              </div>
            </div>

            <div className="flex gap-3">
              <div className="relative mt-1">
                <div className="h-2 w-2 rounded-full bg-blue-500" />
              </div>
              <div className="flex-1 space-y-1">
                <p className="text-sm">Case #00045 status updated</p>
                <p className="text-xs text-muted-foreground">6h ago</p>
              </div>
            </div>

            <div className="flex gap-3">
              <div className="relative mt-1">
                <div className="h-2 w-2 rounded-full bg-green-500" />
              </div>
              <div className="flex-1 space-y-1">
                <p className="text-sm">Document uploaded to Case #00039</p>
                <p className="text-xs text-muted-foreground">8h ago</p>
              </div>
            </div>

            <div className="flex gap-3">
              <div className="relative mt-1">
                <div className="h-2 w-2 rounded-full bg-yellow-500" />
              </div>
              <div className="flex-1 space-y-1">
                <p className="text-sm">Task assigned to Case #00041</p>
                <p className="text-xs text-muted-foreground">1d ago</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}