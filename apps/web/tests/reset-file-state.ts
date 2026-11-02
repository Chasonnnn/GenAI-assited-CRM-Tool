// Runs before each test file. Workers reuse one jsdom window and the dependency module cache
// across files (isolate: false); this file restores the per-file state that isolation provided.
//
// It depends on two Vitest 5 internals: the worker state's evaluated-module map and the
// injected mocker. When either is missing while isolation is off, it throws so that a Vitest
// upgrade cannot silently leak state between files.

type ModuleNode = { promise?: unknown; exports?: unknown; evaluated: boolean; importers: Set<string> }
type Baseline = {
    href: string
    env: Record<string, string | undefined>
    targets: Array<[object, Map<PropertyKey, PropertyDescriptor>]>
}

const runtime = globalThis as typeof globalThis & {
    __vitest_mocker__?: { reset(): void }
    __vitest_worker__?: {
        config: { isolate: boolean }
        evaluatedModules?: { idToModuleMap: Map<string, ModuleNode> }
    }
}

// Module state resets per file, so the baseline lives on the shared global object.
const baselineKey = Symbol.for("crm.tests.fileStateBaseline")

// Globals and prototypes that tests stub; each file starts from the descriptors the first file saw.
const stubbedTargets = (): object[] => [
    globalThis,
    window,
    document,
    navigator,
    Element.prototype,
    HTMLElement.prototype,
    HTMLAnchorElement.prototype,
    HTMLInputElement.prototype,
    HTMLFormElement.prototype,
    Node.prototype,
    Range.prototype,
]

function snapshot(target: object): Map<PropertyKey, PropertyDescriptor> {
    return new Map(Reflect.ownKeys(target).map((key) => [key, Reflect.getOwnPropertyDescriptor(target, key)!]))
}

function sameDescriptor(left: PropertyDescriptor | undefined, right: PropertyDescriptor) {
    return (
        left !== undefined &&
        left.value === right.value &&
        left.get === right.get &&
        left.set === right.set &&
        left.writable === right.writable
    )
}

function restoreGlobals(baseline: Baseline) {
    for (const [target, descriptors] of baseline.targets) {
        for (const [key, descriptor] of descriptors) {
            if (sameDescriptor(Reflect.getOwnPropertyDescriptor(target, key), descriptor)) continue
            // A non-configurable property keeps its value; jsdom marks few of them that way.
            Reflect.defineProperty(target, key, descriptor)
        }
    }
}

function restoreEnv(env: Baseline["env"]) {
    for (const name of Object.keys(process.env)) {
        if (!(name in env)) delete process.env[name]
    }
    Object.assign(process.env, env)
}

function resetBrowserState(baseline: Baseline) {
    window.localStorage.clear()
    window.sessionStorage.clear()
    for (const cookie of document.cookie.split(";")) {
        const name = cookie.split("=", 1)[0]?.trim()
        if (name) document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/`
    }
    window.history.replaceState(null, "", baseline.href)
    document.title = ""
    for (const element of [document.documentElement, document.body]) {
        for (const name of element.getAttributeNames()) element.removeAttribute(name)
    }
    document.head.replaceChildren()
    document.body.replaceChildren()
}

function resetModulesAndMocks() {
    const worker = runtime.__vitest_worker__
    if (!worker || worker.config.isolate) return
    const modules = worker.evaluatedModules?.idToModuleMap
    const mocker = runtime.__vitest_mocker__
    if (!modules || !mocker) {
        throw new Error("tests/reset-file-state.ts cannot reach Vitest's module map or mocker.")
    }
    // Drop the previous file's vi.mock registrations; this file's setup and spec register again.
    mocker.reset()
    // Re-evaluate app modules so each file's mocks apply. Dependencies stay cached; that cache is
    // the speedup over isolated workers.
    modules.forEach((node, path) => {
        if (path.includes("/node_modules/") || path.startsWith("mock:")) return
        node.promise = undefined
        node.exports = undefined
        node.evaluated = false
        node.importers.clear()
    })
}

const baseline = (runtime as { [baselineKey]?: Baseline })[baselineKey]
if (baseline) {
    restoreGlobals(baseline)
    restoreEnv(baseline.env)
    resetBrowserState(baseline)
} else {
    Object.defineProperty(runtime, baselineKey, {
        value: {
            href: window.location.href,
            env: { ...process.env },
            targets: stubbedTargets().map((target) => [target, snapshot(target)]),
        } satisfies Baseline,
    })
}
resetModulesAndMocks()
