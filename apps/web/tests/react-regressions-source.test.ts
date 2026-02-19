import { describe, it, expect } from "vitest"
import { readFileSync } from "node:fs"
import { join } from "node:path"

function readSource(pathFromWebRoot: string): string {
    return readFileSync(join(process.cwd(), pathFromWebRoot), "utf8")
}

describe("React regression guards (source)", () => {
    it("uses stable IDs for editable automation rows", () => {
        const source = readSource("app/(app)/automation/page.tsx")

        expect(source).toContain("key={condition.clientId}")
        expect(source).toContain("key={action.clientId}")
        expect(source).not.toMatch(/conditions\.map\(\(condition, index\) => \(\s*<Card key=\{index\}>/m)
        expect(source).not.toMatch(/actions\.map\(\(action, index\) => \(\s*<Card key=\{index\}>/m)
    })

    it("does not suppress exhaustive deps in MassEditStageModal and handles late stage load", () => {
        const source = readSource("components/surrogates/MassEditStageModal.tsx")

        expect(source).not.toContain("eslint-disable-next-line react-hooks/exhaustive-deps")
        expect(source).toContain("const defaultTargetStageId = React.useMemo")
        expect(source).toContain("if (!open || targetStageId || !defaultTargetStageId) return")
    })

    it("derives open alert count instead of storing duplicate state", () => {
        const source = readSource("app/ops/agencies/[orgId]/page.tsx")

        expect(source).toContain("const openAlertCount = useMemo(")
        expect(source).not.toContain("const [openAlertCount, setOpenAlertCount] = useState")
    })

    it("uses reducer-based local state in CSVUpload", () => {
        const source = readSource("components/import/CSVUpload.tsx")

        expect(source).toContain("const [state, dispatch] = useReducer")
        expect(source).toContain("function csvUploadReducer(")
    })
})
