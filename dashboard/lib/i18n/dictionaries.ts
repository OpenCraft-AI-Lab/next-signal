export const LOCALE_COOKIE = "ns_locale";
export const DEFAULT_LOCALE = "en";
export const LOCALES = ["en", "zh"] as const;

export type Locale = (typeof LOCALES)[number];

export function normalizeLocale(value: string | null | undefined): Locale {
  return value === "zh" ? "zh" : DEFAULT_LOCALE;
}

type CountLabel = (count: number) => string;

export const dictionaries = {
  en: {
    nav: {
      radar: "Radar",
      knowledge: "Knowledge",
      goals: "Goals",
      subscriptions: "Subscriptions",
      design: "Design System",
    },
    language: {
      label: "Interface language",
    },
    settings: {
      trigger: "Settings",
      heading: "Settings",
      subtitle:
        "What next-signal generates, when it runs, and which engine it runs on.",
      saveFailed: "Could not save. Check the dashboard logs.",
      // Deliberately more explicit than a bare "Save": this button writes
      // only a pane's own fields (and, for DeepSeek, its credential) — never
      // which engine is primary, a separate, separately-labeled action.
      save: "Save configuration",
      saving: "Saving…",
      reset: "Reset",
      unsaved: "Unsaved changes",
      apply: "Apply",
      confirm: "Continue",
      cancel: "Cancel",

      railLanguage: "Language",
      railSchedule: "Scheduled runs",
      railEngine: "Engine",
      railRadarEmbedding: "Radar Embedding",
      railKnowledgeEmbedding: "Knowledge Embedding",
      railRss: "RSS",
      railCredentials: "Credentials",

      // Read-only, presence-only summary. Entry happens inline in whichever
      // section actually uses a credential — this list only says what is set.
      credentials: "Credentials",
      credentialsHint:
        "Every credential the sections above resolve, and whether it is set. This list is informational: enter or replace a credential in the section that uses it, not here.",
      credentialsSummary: (set: number, total: number) => `${set}/${total} set`,
      credentialSet: "Set",
      credentialUnset: "Not set",
      credentialPowers: {
        DEEPSEEK_API_KEY:
          "DeepSeek — the Engine section's cloud fallback when the local model is unreachable.",
        RADAR_EMBEDDING_OPENAI_API_KEY:
          "OpenAI, for the Radar Embedding section's OpenAI provider.",
        EMBEDDING_API_KEY:
          "The Radar Embedding section's custom OpenAI-compatible endpoint.",
        OPENAI_API_KEY:
          "OpenAI, for the Knowledge Embedding section's OpenAI provider — independent of the radar dedup key above, even though both are \"an OpenAI key.\"",
        VOYAGE_API_KEY: "Voyage, for the Knowledge Embedding section's Voyage provider.",
        GOOGLE_GENERATIVE_AI_API_KEY:
          "Google, for the Knowledge Embedding section's Google provider.",
        FOLO_TOKEN: "Folo — the radar's article source and the subscriptions page.",
      } as Record<string, string>,

      // RSS section: the Folo credential, moved out of the flat Credentials
      // list into its own section, with the same sign-in assist as before.
      rss: "RSS",
      rssHint:
        "The Folo credential info-radar's article source and the Subscriptions page depend on.",
      credentialEnter: "Enter value",
      credentialReplace: "Enter a new value to replace",
      credentialSave: "Save",
      credentialClear: "Clear",
      credentialSaved: "Credential saved",
      credentialCleared: "Credential cleared",
      credentialUnsetSuffix: "Unset — this will not work.",
      foloConnect: "Sign in to Folo",
      foloWaiting: "Waiting for Folo…",
      foloReopen: "Reopen sign-in",
      foloCancel: "Cancel",
      foloConnected: "Signed in to Folo",
      foloFailed: "Folo sign-in failed",
      foloTimedOut: "Folo sign-in timed out",
      foloHint:
        "Folo has no API-key page, so signing in is the easiest way to get a token. It opens Folo in a new tab and stores the result here. Pasting one manually works too.",
      foloPasteManually: "Paste manually",
      foloManualHint:
        "For a browser that cannot reach the dashboard, or if sign-in fails: paste a Folo session token directly.",

      contentLanguage: "Content language",
      contentLanguageHint:
        "The language radar analyses and wiki frontmatter are written in. The interface language is the toggle in the top bar — the two are independent.",
      contentLanguageSaved: "Content language saved",

      schedule: "Scheduled runs",
      scheduleHint:
        "Pull and analyse the radar unattended at every time listed below.",
      scheduleOn: "On",
      scheduleOff: "Off",
      scheduleTime: "Runs every day at",
      scheduleAdd: "Add",
      scheduleRemoveTime: "Remove this time",
      scheduleNext: (at: string, tz: string) => `Next run today at ${at} · ${tz}`,
      scheduleNextTomorrow: (at: string, tz: string) =>
        `Next run tomorrow at ${at} · ${tz}`,
      scheduleTimezone: "Time zone",
      // Stated, not offered: the same value fixes radar day grouping and review
      // due dates, so it is one environment-wide decision rather than a
      // per-schedule one.
      scheduleTimezoneHint:
        "The zone the times above fire in, read from INFO_RADAR_TIMEZONE. Change it in the environment and restart the stack — radar day grouping follows the same value.",
      scheduleOnMissed: "If a run is missed",
      scheduleOnMissedHint:
        "Catch up runs once for missed times, however many went by — including ones missed while the machine was asleep. Changing the schedule never fires a time that has just passed.",
      scheduleSkip: "Skip",
      scheduleCatchUp: "Catch up",
      scheduleSaved: "Schedule saved",
      scheduleNeverRun: "Has not run yet",
      scheduleRunning: (ago: string) => `Running · started ${ago}`,
      scheduleLastOk: (ago: string) => `Last run ${ago} · succeeded`,
      scheduleLastFailed: (ago: string) => `Last run ${ago} · failed`,

      engine: "Engine",
      engineHint:
        "Which engine next-signal calls. Open a card to configure it, or use it as primary right away.",
      engineUnselectedHint:
        "No engine is selected yet, so next-signal cannot make a chat call. Open a card below and use it as primary.",
      engineSaved: "Engine settings saved",
      enginePrimarySaved: "Engine selection applied",
      engineUsePrimary: "Use as primary",
      enginePrimaryBadge: "Primary",
      engineOmlx: "Local model",
      engineDeepseek: "DeepSeek",
      engineCodex: "Codex CLI",
      engineClaude: "Claude Code CLI",
      engineKindLocal: "on-device",
      engineKindCloud: "cloud API",
      engineKindCli: "local CLI",
      engineStatusKeySet: "Key set",
      engineStatusNoKey: "No API key",
      engineStatusConfigured: "Configured",
      engineStatusUnset: "Not configured",
      engineFallback: "If it is unreachable",
      engineFallbackHint:
        "Where work goes when the engine above cannot be reached.",
      engineFallbackNone: "Nothing — fail loudly",
      engineFallbackSaved: "Fallback saved",

      omlxEndpoint: "Endpoint",
      omlxModel: "Model",
      omlxParallel: "Parallel requests",
      omlxHint:
        "Runs on your own machine — nothing is billed and nothing leaves it. Any OpenAI-compatible server works; a single one rarely parallelises cleanly, so keep this low.",
      omlxEndpointHint:
        "Leave it empty if you are not running a local model — profiles fall back to the cloud. Scheduled runs and new commands use a change immediately; agents already running inside AgentOS pick it up when that process restarts.",

      deepseekModel: "Model",
      deepseekReasoning: "Reasoning",
      deepseekOff: "Off",
      deepseekLow: "Low",
      deepseekHigh: "High",
      deepseekHint:
        "Billed per token. Reasoning bills thinking tokens as output — Low keeps some chain-of-thought without the full cost.",
      deepseekKeyHint: "Enter your DeepSeek API key below. A saved key applies to the next run.",

      codexModel: "Model",
      codexEffort: "Reasoning effort",
      codexSpeed: "Speed",
      codexRequired: "Required",
      codexSelect: "Select…",
      codexStandard: "Standard",
      codexFast: "Fast",
      codexHint:
        "Model, effort, and speed must be selected before next-signal can call Codex. Fast uses more credits on supported models.",
      codexSaved: "Codex settings saved",

      claudeModel: "Model",
      claudeEffort: "Thinking effort",
      claudeHint:
        "Model and effort must be selected before next-signal can call Claude Code. Available effort levels depend on the selected model.",
      claudeSaved: "Claude settings saved",

      embedding: "Radar Embedding",
      embeddingHint:
        "Which embedder the radar's duplicate check uses. This choice is permanent for this install once saved — pick one, save, and confirm.",
      embeddingSaved: "Embedding settings saved",
      embeddingUnselectedHint:
        "No embedder is selected, so the duplicate check is off — the radar still pulls, scores, and shows everything, you will just see repeats of the same story. Fill in one of the options below and save it to turn deduplication on.",
      embeddingIdentityNone: "none — deduplication is off",
      embeddingConfirmPermanent:
        "This embedder cannot be changed once saved. A different model would produce vectors that cannot be compared against ones already stored, so this section locks after this save. Continue?",
      embeddingLockedHint:
        "This section is locked: an embedder has been selected and saved, and cannot be changed or reconfigured.",
      embeddingSaveToSelectHint:
        "Save to store these settings and start using this embedder.",
      embeddingOmlx: "Local model",
      embeddingOpenai: "OpenAI",
      embeddingCompatible: "Custom endpoint",
      embeddingKindEndpoint: "OpenAI-compatible API",
      embeddingIdentity: "Active vector space",
      embeddingIdentityHint:
        "The identity stamped on every new vector. The duplicate check only compares vectors carrying this exact value.",
      embeddingLegacyHint:
        "Topics stored before this setting existed are labelled legacy:unknown and stay parked: the old schema never recorded which model produced them, and guessing would compare unrelated vectors. Relabelling them is a deliberate manual SQL step — see docs/operations.md.",
      embeddingOmlxHint:
        "Runs on your own machine — nothing is billed and nothing leaves it. Embedding shares the local GPU limit with on-device inference.",
      embeddingOmlxEndpointHint:
        "The embedding server's own address, separate from the Engine section's local endpoint: one local model server holds one model, so a chat model and an embedding model are two ports.",
      embeddingHostedHint:
        "Hosted: each radar summary is sent to this endpoint, and every item can be billed — including unattended scheduled runs.",
      embeddingOpenaiKeyHint:
        "Enter your OpenAI key below — this is separate from the Knowledge Embedding section's OpenAI key. A saved key applies to the next item.",
      embeddingWidthHint:
        "The request asks for 1024 values. A model that cannot return exactly 1024 is rejected at call time rather than reshaped.",
      embeddingBaseUrl: "API root",
      embeddingBaseUrlHint:
        "A plain API root such as https://host.example/v1 — the /embeddings route is appended for you. A key or parameter inside the URL is rejected.",
      embeddingCompatibleKeyHint:
        "Enter your endpoint's key below. A saved key applies to the next item.",
      embeddingSpaceId: "Vector space id",
      embeddingSpaceIdHint:
        "Your own name for the vectors this endpoint produces. Change it whenever the weights, tokenizer, pooling, or quantization change; moving the same service to a new URL does not need a new id.",
      embeddingCompatibleSaveHint:
        "This endpoint is not in use yet. Save all fields, including the key, to store it and switch to it.",

      knowledgeEmbedding: "Knowledge Embedding",
      knowledgeEmbeddingHint:
        "GBrain's embedding provider for knowledge-base search — independent of the Radar Embedding section above. Nothing is selected until GBrain is initialized, and the choice is permanent once it is.",
      knowledgeEmbeddingUnselectedHint:
        "GBrain is not initialized, so knowledge search is unavailable. Choose a provider and model below and initialize it.",
      knowledgeEmbeddingSaved: "GBrain initialized",
      knowledgeEmbeddingOpenai: "OpenAI",
      knowledgeEmbeddingVoyage: "Voyage",
      knowledgeEmbeddingGoogle: "Google",
      knowledgeEmbeddingOllama: "Ollama",
      knowledgeEmbeddingLmstudio: "LM Studio",
      knowledgeEmbeddingLlamaServer: "llama-server",
      knowledgeEmbeddingKindLocal: "local runner",
      knowledgeEmbeddingKindHosted: "cloud API",
      knowledgeEmbeddingModel: "Model",
      knowledgeEmbeddingModelHint: "GBrain's model identifier, e.g. text-embedding-3-large.",
      knowledgeEmbeddingStatusNotInitialized: "Not initialized",
      knowledgeEmbeddingStatusCredentialMissing: "Credential missing",
      knowledgeEmbeddingStatusReady: "Ready",
      knowledgeEmbeddingStatusIndeterminate:
        "Cannot determine GBrain's state right now",
      knowledgeEmbeddingConfirmPermanent:
        "This initializes GBrain with this embedding model. The model sizes GBrain's database schema permanently — it cannot be changed afterward without a destructive migration outside this dashboard. Continue?",
      knowledgeEmbeddingInitializing: "Initializing GBrain…",
      knowledgeEmbeddingInitFailed: "GBrain initialization failed",
      knowledgeEmbeddingAlreadyInitialized:
        "GBrain is already initialized with a different model and cannot be reinitialized here.",
      knowledgeEmbeddingLockedHint:
        "This section is locked: GBrain has been initialized and its embedding model cannot be changed.",
      knowledgeEmbeddingSaveToInitHint:
        "Save to initialize GBrain with this provider and model. This runs next-signal knowledge gbrain-init and can take a moment.",
      knowledgeEmbeddingCredentialHint:
        "Enter the provider's key below. GBrain cannot be initialized with this provider until it is saved.",
      knowledgeEmbeddingLocalHint:
        "Local runners need no credential — GBrain reaches this provider directly.",

      authAccount: "CLI account",
      authConnected: "Connected",
      authNotConnected: "Not connected",
      authUnavailable: "CLI unavailable",
      authConnecting: "Connecting…",
      authConnect: "Connect",
      authReconnect: "Reconnect",
      authDisconnect: "Disconnect",
      authDisconnected: "CLI account disconnected",
      authCancel: "Cancel login",
      authStarted: "Login started",
      authFailed: "Authentication failed",
      authHint:
        "Login is saved in the provider's own Docker volume. The dashboard can only run the fixed login, status, and logout commands.",
      authOpenLogin: "Open login page",
      authCopyLink: "Copy link",
      authLinkCopied: "Login link copied",
      authCodePlaceholder: "Paste the Claude authorization code",
      authSubmitCode: "Submit code",
      authCodeSent: "Authorization code submitted",
    },
    theme: {
      toggle: "Toggle theme",
    },
    relativeTime: {
      never: "never",
      invalid: "-",
      justNow: "just now",
      seconds: (count: number) => `${count}s ago`,
      minutes: (count: number) => `${count}m ago`,
      hours: (count: number) => `${count}h ago`,
      days: (count: number) => `${count}d ago`,
      months: (count: number) => `${count}mo ago`,
    },
    radar: {
      title: "Radar",
      todaySubtitle: (count: number) =>
        `High-signal items from today's analysis run · ${count} kept`,
      daySubtitle: (day: string, count: number) =>
        `Items from ${day} · ${count} kept`,
      noItemsPrefix:
        "No items match these filters. Try lowering the score threshold",
      noItemsNovel: " or turning off Novel only",
      noItemsLastFeed: " or turning off Last feed",
      noItemsSuffix: ".",
      pastDays: "Past days",
      pastDaysSub: 'grouped by calendar day · click "Show all" to open',
      appendixTitle: "Full analysis",
      detail: {
        back: "Back to radar",
        unanalyzed: "This radar item has not been analyzed yet.",
        summary: "Summary",
        impact: "Impact",
        tier1Reason: "Tier-1 reason",
        notAnalyzed: "Not analyzed",
        contentStatus: "Content status",
        dedup: "Dedup",
        duplicateOf: (summary: string) => `of "${summary}"`,
        source: "Source · radar_items.excerpt",
        openOriginal: "Open original",
        noExcerpt: "No excerpt captured.",
      },
      filters: {
        todayTitle: "Today's high-signal items",
        itemsTitle: "Items",
        shownOf: (shown: number, total: number) =>
          `${shown} of ${total} shown · verdict = keep`,
        sort: {
          "score-desc": "Score ↓",
          "score-asc": "Score ↑",
          newest: "Newest",
        },
        novelOnly: "Novel only",
        novelOnlyTitle:
          "Hide items the dedup gate flagged as duplicates of earlier topics",
        lastFeed: "Last feed",
        lastFeedTitle:
          "Show only items from the latest Pull + Analyze click (5-min cluster)",
        score: "Score >= ",
        downloadMd: "Download the current view as markdown",
        downloadPdf: "Download the current view as PDF",
        backToday: "Back to today",
        backTodayTitle: (today: string) => `Back to today (${today})`,
      },
      tracker: {
        today: "today",
        lastFeed: "last feed",
        lastFeedTitle: "Counting only items from the latest pull + analyze run",
        pulled: "Pulled",
        sources: (count: number) => `${count} sources`,
        t1Dropped: "T1 dropped",
        t1DroppedTitle: "Items the Tier-1 relevance filter rejected",
        t1Kept: "T1 kept",
        t1KeptTitle: "Items passed by Tier-1 -> fed into Tier-2 fetch+analysis",
        t2Full: "T2 full",
        t2FullTitle: "Tier-2 fetched full content and analyzed successfully",
        fallback: "fallback",
        fallbackTitle: "Tier-2 fell back to feed summary (full fetch failed)",
        error: "error",
        errorTitle: "Tier-2 fetch or analysis errored",
        novel: "Novel",
        duplicateShort: "Dup",
        histogram: "Score distribution · 0-100",
        histogramTitle: (range: string, count: number) =>
          `${range}: ${count} items`,
      },
      pullAnalyze: {
        pulled: "pulled",
        analyzed: "analyzed",
        pending: "pending",
        pulling: "Pulling...",
        idle: "Pull + Analyze",
        lastPullTitle:
          "New items inserted by the most recent Pull + Analyze click (0 means the click registered but found nothing new)",
        analyzedTitle:
          "Items processed by the analyzer in the latest cluster (5-min gap)",
        drainedTitle:
          "Last pull produced items the analyzer hasn't processed yet - re-trigger to drain",
      },
      progress: {
        analyzing: (done: number, total: number) =>
          `Analyzing ${done}/${total}`,
        title: "Items processed by the running analyze pass",
      },
      card: {
        readSource: "Read source",
        showLess: "Show less",
        expandImpact: "Expand impact",
      },
      badges: {
        dedupMissingTitle: "Dedup status not recorded",
        duplicate: "duplicate",
        novel: "novel",
        contentMissingTitle: "Tier-2 fetch did not run",
        full: "full",
        fallback: "fallback",
        error: "error",
      },
      dayGroup: {
        kept: (count: number) => `${count} kept`,
        median: "median",
        noHeadline: "No headline",
        showing: (top: number, total: number) =>
          `Showing top ${top} of ${total} kept items · click to open detail`,
        showAll: (count: number) => `Show all ${count} ->`,
      },
      pager: {
        outside: (count: number) =>
          `This item is outside the current filter (${count} item${count === 1 ? "" : "s"} match).`,
        notInFilter: (count: number) => `not in filter · ${count} match`,
        nextItem: (remaining: number) =>
          `Next item · ${remaining} left to view`,
        last: "You've reached the last item.",
        of: (index: number, total: number) => `${index} of ${total}`,
        left: (count: number) => (count > 0 ? `${count} left` : "last item"),
        previousTitle: (title: string) => `Previous · ${title}`,
        noPrevious: "No previous item",
        nextTitle: (title: string) => `Next · ${title}`,
        next: "Next",
        noMore: "No more items",
      },
      ingest: {
        idle: "Ingest",
        pending: "Starting...",
      },
      recap: {
        title: "Smart Recap",
        subtitle: "Synthesize a range of signals into themes",
        verb: "Recap",
        last7: "Last 7 days",
        last30: "Last 30 days",
        custom: "Custom",
        from: "From",
        to: "To",
        generate: "Generate recap",
        regenerate: "Regenerate",
        generating: "Synthesizing...",
        pending: "Starting...",
        none: "No recap for this range yet.",
        empty: "No signals cleared the filter in this range.",
        badRange: "Invalid range.",
        failed: (message: string) => `Recap failed: ${message}`,
        stale: (count: number) =>
          `${count} signal${count === 1 ? "" : "s"} analyzed since this recap`,
        coverage: (shown: number, considered: number) =>
          `Synthesized from the top ${shown} of ${considered} signals`,
        cited: (count: number) => `${count} source${count === 1 ? "" : "s"}`,
        sweptCitation: "source no longer retained",
        savedTitle: "Saved recaps",
        savedSub: "click any to reopen it above",
        savedSignals: (count: number) =>
          `${count} signal${count === 1 ? "" : "s"}`,
        savedNovel: "novel",
      },
    },
    knowledge: {
      title: "Knowledge",
      subtitle: "GBrain wiki · ANN search over ingested items",
      searchPlaceholder: "Search the wiki (ANN)...",
      clickResult: "Click a result to preview.",
      selectDoc: "Select a doc from the tree, or search the wiki.",
      preview: "Preview",
      updated: (date: string) => `updated ${date}`,
      noMatches: (query: string) => `No matches for "${query}".`,
      resultsFor: (count: number, query: string) =>
        `${count} results for "${query}"`,
      directory: "Wiki directory",
      review: {
        title: "Review",
        subtitle: "Spaced repetition over your saved docs",
        due: (count: number) => `${count} due`,
        nothingDue: "Nothing due for review.",
        more: (count: number) => `${count} more due`,
        position: (n: number, total: number) => `Review ${n} of ${total}`,
        captured: (date: string) => `captured ${date}`,
        seen: "Got it",
        seenPending: "Saving…",
        seenFailed: "Couldn't save — try again",
        refresh: "Refresh",
        refreshPending: "Refreshing…",
        refreshVerb: "Review refresh",
        refreshStarted: "Review refresh started",
        refreshToastTitle: "Refreshing reviews…",
        refreshToastDescription:
          "Reconciling the wiki and generating recall points",
        curve: (count: number) => `Ebbinghaus curve · ${count} docs`,
        curveDone: "done",
        curveDueKey: "due",
        curveScheduledKey: "scheduled",
        curveEnrolled: "enrolled",
        curveMedian: "median stage",
        curveMedianTitle: "The stage the middle doc is waiting on",
        curveDoneStatTitle: "Past the final stage — no longer scheduled",
        curveTitle: (stage: string, total: number, due: number) =>
          `${stage}: ${total} docs, ${due} due`,
        curveDoneTitle: (total: number) =>
          `Past the final stage: ${total} docs`,
      },
      reindex: {
        idle: "Re-index",
        pending: "Re-indexing...",
        toastTitle: "Re-indexing knowledge...",
        toastDescription: "Rebuilding ANN vectors",
      },
      ingest: {
        heading: "Ingest a link",
        placeholder: "Paste a URL or staged file path...",
        folderLabel: "Folder",
        autoClassify: "Auto-classify",
        submit: "Ingest",
        submitting: "Starting...",
        started: "Ingest started",
        errorEmpty: "Enter a URL or staged file path first",
        activeTitle: "Active ingests",
        source: { knowledge: "manual", radar: "radar" },
        steps: {
          fetch: "Fetch",
          clean: "Clean",
          enrich: "Enrich",
          classify: "Classify",
          persist: "Persist",
        },
        done: "Done",
        failed: "Failed",
        savedTo: (p: string) => `Saved to ${p}`,
        category: (category: string) => `Category: ${category}`,
        indexed: "Indexed in GBrain",
        indexFailed: "GBrain index failed",
      },
      manage: {
        newFolder: "New folder",
        newFolderTitle: "Create a folder",
        newFolderDesc:
          "Adds a wiki folder and registers it as an ingest destination.",
        pathLabel: "Path",
        pathPlaceholder: "e.g. investing/quant",
        pathHint: "Lowercase slug path; segments split by /",
        scopeLabel: "Scope (optional)",
        scopePlaceholder: "What belongs here — guides auto-classify",
        freshnessLabel: "Default freshness (optional)",
        freshnessNone: "— none —",
        create: "Create",
        creating: "Creating...",
        folderCreated: (p: string) => `Created ${p}`,
        deleteFile: "Delete file",
        deleteFolder: "Delete folder",
        deleteFileTitle: "Delete file",
        deleteFolderTitle: "Delete folder",
        deleteFileBody: (name: string) =>
          `Delete “${name}”? The wiki file is removed; the GBrain index stays until the next re-index.`,
        deleteFolderBody: (name: string, count: number) =>
          `Delete folder “${name}” and its ${count} document(s)? This cannot be undone.`,
        cancel: "Cancel",
        confirmDelete: "Delete",
        deleting: "Deleting...",
        deleted: (name: string) => `Deleted ${name}`,
        errorPath: "Enter a folder path",
        errorPathChars: "Path may only contain a-z, 0-9, /, _ and -",
        errorExists: "That folder already exists",
        errorNotFound: "Not found",
      },
    },
    goals: {
      title: "Goals",
      subtitle: (count: number) =>
        `Steers Tier-1 filtering & scoring · goals.yaml in user state · ${count} goals`,
      missing: "No goals file yet",
      attention: "goals.yaml needs attention",
      help: (message: string, path: string) =>
        `${message}. Add the first goal below, or start from the shipped examples in ${path}.`,
      emptyTitle: "No goals configured",
      emptyBody:
        "Tier-1 filtering and Tier-2 scoring both need at least one goal. Analysis will fail until you add one — including unattended scheduled runs.",
      startFromExample: "Start from example",
      viewExamples: "View examples",
      viewExamplesHint: "Shipped reference goals, read-only",
      fields: {
        name: "name",
        nameHintReadOnly: "slug · read-only",
        nameHintNew: "kebab-case slug",
        description: "description",
        topics: "topics",
        keywords: "keywords",
        addPlaceholder: "add...",
      },
      removeTitle: (item: string) => `Remove ${item}`,
      deleteConfirm: (name: string) => `Delete goal "${name}"?`,
      topicKeywordCount: (topics: number, keywords: number) =>
        `${topics}t · ${keywords}kw`,
      edit: "Edit",
      delete: "Delete",
      cancel: "Cancel",
      saveChanges: "Save changes",
      saveGoal: "Save goal",
      addGoal: "Add goal",
      messages: {
        notFound: (name: string) => `Goal not found: ${name}`,
        saved: (name: string) => `Saved ${name}`,
        invalidName: "Goal name must be kebab-case",
        exists: (name: string) => `Goal already exists: ${name}`,
        added: (name: string) => `Added ${name}`,
        deleted: (name: string) => `Deleted ${name}`,
        seeded: (count: number) => `Added ${count} example goal(s)`,
        seedRefused:
          "Goals are already configured — clear them first, or add goals individually",
      },
    },
    subscriptions: {
      title: "Subscriptions",
      subtitle: (feeds: number, unread: number) =>
        `Read-only · folocli subscription list · ${feeds} feeds · ${unread} unread`,
      loadingSubtitle: "Read-only · folocli subscription list",
      loading:
        "folocli cold start - fetching subscription list (can take 30s+)...",
      unable: "Unable to load Folo subscriptions",
      checkAuth: (message: string) =>
        `${message}. Check Folo auth with uv run next-signal doctor.`,
      empty: "Folo returned no subscriptions.",
      all: "All",
      searchPlaceholder: "Search feeds...",
      titleColumn: "Title",
      feedUrl: "Feed URL",
      category: "Category",
      unread: "Unread",
      noFeedUrl: "no feed URL",
      noMatches: (query: string) =>
        `No feeds match ${query ? `"${query}"` : "these filters"}.`,
    },
    design: {
      title: "Design System",
      subtitle:
        "Live tokens - violet primary · reacts to the theme toggle in the nav",
      tabs: {
        tokens: "Tokens",
        components: "Components",
        states: "States",
        brand: "Brand",
      },
    },
    actions: {
      urlMissing: "URL missing or malformed",
      ingestStarted: "Ingest started",
      analyzeStarted: "Analyze started",
      pullCompleteAnalyzeStarted: "Pull complete · analyze started",
      analyzeAlreadyRunning: "Pull complete · analyze already running",
      reindexStarted: "Re-index started",
    },
  },
  zh: {
    nav: {
      radar: "雷达",
      knowledge: "知识库",
      goals: "目标",
      subscriptions: "订阅",
      design: "设计系统",
    },
    language: {
      label: "界面语言",
    },
    settings: {
      trigger: "设置",
      heading: "设置",
      subtitle: "next-signal 生成什么、什么时候跑、用哪个引擎跑。",
      saveFailed: "保存失败，请查看 dashboard 日志。",
      save: "保存配置",
      saving: "保存中…",
      reset: "还原",
      unsaved: "有未保存的改动",
      apply: "应用",
      confirm: "继续",
      cancel: "取消",

      railLanguage: "语言",
      railSchedule: "定时运行",
      railEngine: "模型引擎",
      railRadarEmbedding: "雷达向量嵌入",
      railKnowledgeEmbedding: "知识库向量嵌入",
      railRss: "RSS",
      railCredentials: "凭据",

      // 只读、只显示是否配置的汇总。填写凭据的地方在用到它的那个功能区块里，
      // 不在这里。
      credentials: "凭据",
      credentialsHint:
        "上面各区块会用到的每个凭据，以及是否已配置。这个列表只做展示——要填写或替换凭据，去用到它的那个区块，不在这里填。",
      credentialsSummary: (set: number, total: number) => `已配置 ${set}/${total}`,
      credentialSet: "已配置",
      credentialUnset: "未配置",
      credentialPowers: {
        DEEPSEEK_API_KEY: "DeepSeek——「模型引擎」一节本地模型不可达时的云端回落。",
        RADAR_EMBEDDING_OPENAI_API_KEY: "OpenAI，供「雷达向量嵌入」一节的 OpenAI provider 使用。",
        EMBEDDING_API_KEY: "「雷达向量嵌入」一节的自定义 OpenAI 兼容端点。",
        OPENAI_API_KEY:
          "OpenAI，供「知识库向量嵌入」一节的 OpenAI provider 使用——虽然都叫「OpenAI key」，但和上面雷达去重用的那把是两回事。",
        VOYAGE_API_KEY: "Voyage，供「知识库向量嵌入」一节的 Voyage provider 使用。",
        GOOGLE_GENERATIVE_AI_API_KEY:
          "Google，供「知识库向量嵌入」一节的 Google provider 使用。",
        FOLO_TOKEN: "Folo——雷达的文章来源，以及订阅页。",
      } as Record<string, string>,

      // RSS 一节：Folo 凭据从原来那个扁平「凭据」列表挪到了自己的区块，登录
      // 辅助流程不变。
      rss: "RSS",
      rssHint: "info-radar 的文章来源和订阅页都要用的 Folo 凭据。",
      credentialEnter: "填入值",
      credentialReplace: "填入新值以替换",
      credentialSave: "保存",
      credentialClear: "清除",
      credentialSaved: "凭据已保存",
      credentialCleared: "凭据已清除",
      credentialUnsetSuffix: "未配置——这项功能用不了。",
      foloConnect: "登录 Folo",
      foloWaiting: "等待 Folo 授权…",
      foloReopen: "重新打开登录页",
      foloCancel: "取消",
      foloConnected: "已登录 Folo",
      foloFailed: "Folo 登录失败",
      foloTimedOut: "Folo 登录超时",
      foloHint:
        "Folo 没有 API key 页面，所以登录是拿 token 最省事的方式。会新开一个标签页打开 Folo，拿到后直接存到这里。手动粘贴也行。",
      foloPasteManually: "手动粘贴",
      foloManualHint: "浏览器连不上 dashboard，或登录失败时：直接粘贴一个 Folo session token。",

      contentLanguage: "内容语言",
      contentLanguageHint:
        "雷达分析和知识库 frontmatter 的写作语言。界面语言是顶栏那个开关，两者互不影响。",
      contentLanguageSaved: "内容语言已保存",

      schedule: "定时运行",
      scheduleHint: "在下面列出的每个时间点无人值守地拉取并分析雷达。",
      scheduleOn: "开启",
      scheduleOff: "关闭",
      scheduleTime: "每天运行于",
      scheduleAdd: "添加",
      scheduleRemoveTime: "移除这个时间",
      scheduleNext: (at: string, tz: string) => `下一次：今天 ${at}（${tz}）`,
      scheduleNextTomorrow: (at: string, tz: string) =>
        `下一次：明天 ${at}（${tz}）`,
      scheduleTimezone: "时区",
      scheduleTimezoneHint:
        "上面的时间按这个时区触发，取自 INFO_RADAR_TIMEZONE。要改就改环境变量再重启整个栈——雷达的按天分组用的是同一个值。",
      scheduleOnMissed: "错过某次运行时",
      scheduleOnMissedHint:
        "补跑会为错过的时间点补一次，不管错过了几次——包括机器睡眠期间错过的。改动计划本身永远不会触发刚过去的时间点。",
      scheduleSkip: "跳过",
      scheduleCatchUp: "补跑",
      scheduleSaved: "计划已保存",
      scheduleNeverRun: "尚未运行",
      scheduleRunning: (ago: string) => `正在运行·开始于 ${ago}`,
      scheduleLastOk: (ago: string) => `上次运行 ${ago}·成功`,
      scheduleLastFailed: (ago: string) => `上次运行 ${ago}·失败`,

      engine: "模型引擎",
      engineHint:
        "next-signal 调用哪个引擎。点开一张卡片配置它，或者直接把它设为主引擎。",
      engineUnselectedHint: "还没选引擎，next-signal 没法发起对话调用。点开下面一张卡片，设为主引擎。",
      engineSaved: "引擎设置已保存",
      enginePrimarySaved: "引擎选择已应用",
      engineUsePrimary: "设为主引擎",
      enginePrimaryBadge: "主引擎",
      engineOmlx: "本地模型",
      engineDeepseek: "DeepSeek",
      engineCodex: "Codex CLI",
      engineClaude: "Claude Code CLI",
      engineKindLocal: "本机推理",
      engineKindCloud: "云端 API",
      engineKindCli: "本地 CLI",
      engineStatusKeySet: "密钥已配置",
      engineStatusNoKey: "缺少 API 密钥",
      engineStatusConfigured: "已配置",
      engineStatusUnset: "未配置",
      engineFallback: "连不上时",
      engineFallbackHint: "上面的引擎连不上时，任务转到哪里。",
      engineFallbackNone: "不回落（直接失败）",
      engineFallbackSaved: "回落设置已保存",

      omlxEndpoint: "端点",
      omlxModel: "模型",
      omlxParallel: "并发请求",
      omlxHint:
        "跑在你自己的机器上——不计费，数据不出本机。任何 OpenAI 兼容的服务都可以；单个服务通常并行不干净，这个值保持小一点。",
      omlxEndpointHint:
        "没在本地跑模型就留空——相关 profile 会回落到云端。改动对定时任务和新命令立即生效；AgentOS 里已经跑起来的 agent 要等该进程重启才会用上。",

      deepseekModel: "模型",
      deepseekReasoning: "推理",
      deepseekOff: "关闭",
      deepseekLow: "低",
      deepseekHigh: "高",
      deepseekHint:
        "按 token 计费。推理会把思考 token 算进输出——「低」保留一部分思考链但不吃满成本。",
      deepseekKeyHint: "在下面填入你的 DeepSeek API key。保存后下次运行即生效。",

      codexModel: "模型",
      codexEffort: "推理强度",
      codexSpeed: "速度",
      codexRequired: "必填",
      codexSelect: "请选择…",
      codexStandard: "标准",
      codexFast: "快速",
      codexHint:
        "必须先选择模型、推理强度和速度，next-signal 才能调用 Codex；支持的模型使用快速模式会消耗更多额度。",
      codexSaved: "Codex 设置已保存",

      claudeModel: "模型",
      claudeEffort: "思考强度",
      claudeHint:
        "必须先选择模型和思考强度，next-signal 才能调用 Claude Code；可用的思考强度取决于所选模型。",
      claudeSaved: "Claude 设置已保存",

      embedding: "雷达向量嵌入",
      embeddingHint:
        "雷达的去重判断用哪个嵌入模型。保存后这个选择对本次部署是永久的——选一个，保存，并确认。",
      embeddingSaved: "嵌入设置已保存",
      embeddingUnselectedHint:
        "还没有选嵌入模型，所以去重是关着的——雷达照常抓取、打分、展示，只是同一件事会重复出现。在下面任选一项填好并保存，去重就会打开。",
      embeddingIdentityNone: "无 —— 去重已关闭",
      embeddingConfirmPermanent:
        "这个嵌入模型一旦保存就无法更改——换一个模型会产生和已存向量不可比较的新向量，所以这一节在保存后就会锁定。要继续吗？",
      embeddingLockedHint: "这一节已锁定：嵌入模型已选定并保存，无法再更改或重新配置。",
      embeddingSaveToSelectHint: "保存后即存下这些设置，并开始使用这个嵌入模型。",
      embeddingOmlx: "本地模型",
      embeddingOpenai: "OpenAI",
      embeddingCompatible: "自定义端点",
      embeddingKindEndpoint: "OpenAI 兼容 API",
      embeddingIdentity: "当前向量空间",
      embeddingIdentityHint:
        "打在每条新向量上的身份标识。去重只会比较带着这个完全相同取值的向量。",
      embeddingLegacyHint:
        "这个设置出现之前存下的主题标为 legacy:unknown 并保持搁置：旧表结构没记录是哪个模型产生的，猜一个就等于去比较毫不相干的向量。要重新打标是一步刻意的手工 SQL——见 docs/operations.md。",
      embeddingOmlxHint:
        "跑在你自己的机器上——不计费，数据不出本机。嵌入和本机推理共用同一个本地 GPU 并发上限。",
      embeddingOmlxEndpointHint:
        "嵌入服务自己的地址，和「引擎」一节的本地端点是两回事：一个本地模型服务只挂一个模型，所以对话模型和嵌入模型是两个端口。",
      embeddingHostedHint:
        "云端：每条雷达摘要都会发到这个端点，每个条目都可能计费——包括无人值守的定时运行。",
      embeddingOpenaiKeyHint:
        "在下面填入你的 OpenAI key——和「知识库向量嵌入」一节的 OpenAI key 是两回事。保存后下一条就生效。",
      embeddingWidthHint:
        "请求会要 1024 个值。返回不是正好 1024 的模型会在调用时被拒绝，而不是被截断或补齐。",
      embeddingBaseUrl: "API 根地址",
      embeddingBaseUrlHint:
        "填 API 根地址，例如 https://host.example/v1——/embeddings 这段由程序自己拼。URL 里带密钥或参数会被拒绝。",
      embeddingCompatibleKeyHint: "在下面填入这个端点的 key。保存后下一条就生效。",
      embeddingSpaceId: "向量空间 id",
      embeddingSpaceIdHint:
        "你自己给这个端点产出的向量起的名字。权重、分词器、pooling 或量化变了就换一个；同一个服务换个 URL 不需要换 id。",
      embeddingCompatibleSaveHint:
        "这个端点还没启用。所有字段（含 key）都填好并保存，才会存下来并切过去。",

      knowledgeEmbedding: "知识库向量嵌入",
      knowledgeEmbeddingHint:
        "GBrain 知识库搜索用的嵌入 provider——和上面「雷达向量嵌入」一节相互独立。GBrain 初始化之前什么都不会选中，一旦初始化，这个选择就是永久的。",
      knowledgeEmbeddingUnselectedHint:
        "GBrain 还没初始化，知识库搜索用不了。在下面选一个 provider 和模型并初始化。",
      knowledgeEmbeddingSaved: "GBrain 已初始化",
      knowledgeEmbeddingOpenai: "OpenAI",
      knowledgeEmbeddingVoyage: "Voyage",
      knowledgeEmbeddingGoogle: "Google",
      knowledgeEmbeddingOllama: "Ollama",
      knowledgeEmbeddingLmstudio: "LM Studio",
      knowledgeEmbeddingLlamaServer: "llama-server",
      knowledgeEmbeddingKindLocal: "本地运行",
      knowledgeEmbeddingKindHosted: "云端 API",
      knowledgeEmbeddingModel: "模型",
      knowledgeEmbeddingModelHint: "GBrain 的模型标识符，例如 text-embedding-3-large。",
      knowledgeEmbeddingStatusNotInitialized: "未初始化",
      knowledgeEmbeddingStatusCredentialMissing: "缺少凭据",
      knowledgeEmbeddingStatusReady: "已就绪",
      knowledgeEmbeddingStatusIndeterminate: "暂时无法判断 GBrain 的状态",
      knowledgeEmbeddingConfirmPermanent:
        "这会用这个嵌入模型初始化 GBrain。模型会永久决定 GBrain 数据库表结构的大小——之后不能改，除非在这个 dashboard 之外做一次破坏性迁移。要继续吗？",
      knowledgeEmbeddingInitializing: "正在初始化 GBrain…",
      knowledgeEmbeddingInitFailed: "GBrain 初始化失败",
      knowledgeEmbeddingAlreadyInitialized: "GBrain 已经用别的模型初始化过，这里没法重新初始化。",
      knowledgeEmbeddingLockedHint: "这一节已锁定：GBrain 已初始化，嵌入模型无法更改。",
      knowledgeEmbeddingSaveToInitHint:
        "保存后会用这个 provider 和模型初始化 GBrain。这一步会跑 next-signal knowledge gbrain-init，可能要等一会儿。",
      knowledgeEmbeddingCredentialHint:
        "在下面填入这个 provider 的 key。key 存好之前没法用这个 provider 初始化 GBrain。",
      knowledgeEmbeddingLocalHint: "本地运行的 provider 不需要凭据，GBrain 直接连它。",

      authAccount: "CLI 账号",
      authConnected: "已连接",
      authNotConnected: "未连接",
      authUnavailable: "CLI 不可用",
      authConnecting: "连接中…",
      authConnect: "连接",
      authReconnect: "重新连接",
      authDisconnect: "断开连接",
      authDisconnected: "CLI 账号已断开",
      authCancel: "取消登录",
      authStarted: "已开始登录",
      authFailed: "认证失败",
      authHint:
        "登录信息保存在 provider 自己的 Docker volume 中。Dashboard 只能运行固定的登录、状态和退出命令。",
      authOpenLogin: "打开登录页面",
      authCopyLink: "复制链接",
      authLinkCopied: "登录链接已复制",
      authCodePlaceholder: "粘贴 Claude 授权码",
      authSubmitCode: "提交授权码",
      authCodeSent: "授权码已提交",
    },
    theme: {
      toggle: "切换主题",
    },
    relativeTime: {
      never: "从未",
      invalid: "-",
      justNow: "刚刚",
      seconds: (count: number) => `${count} 秒前`,
      minutes: (count: number) => `${count} 分钟前`,
      hours: (count: number) => `${count} 小时前`,
      days: (count: number) => `${count} 天前`,
      months: (count: number) => `${count} 个月前`,
    },
    radar: {
      title: "雷达",
      todaySubtitle: (count: number) =>
        `今天分析筛出的高信号条目 · 保留 ${count} 条`,
      daySubtitle: (day: string, count: number) =>
        `${day} 的条目 · 保留 ${count} 条`,
      noItemsPrefix: "没有条目匹配当前过滤条件。可以降低分数阈值",
      noItemsNovel: "，或关闭“仅新主题”",
      noItemsLastFeed: "，或关闭“最近一次抓取”",
      noItemsSuffix: "。",
      pastDays: "历史日期",
      pastDaysSub: "按自然日分组 · 点击“显示全部”打开",
      appendixTitle: "完整分析",
      detail: {
        back: "返回雷达",
        unanalyzed: "这个雷达条目还没有完成分析。",
        summary: "摘要",
        impact: "影响",
        tier1Reason: "Tier-1 理由",
        notAnalyzed: "未分析",
        contentStatus: "内容状态",
        dedup: "去重",
        duplicateOf: (summary: string) => `重复自“${summary}”`,
        source: "来源 · radar_items.excerpt",
        openOriginal: "打开原文",
        noExcerpt: "没有抓取到摘录。",
      },
      filters: {
        todayTitle: "今天的高信号条目",
        itemsTitle: "条目",
        shownOf: (shown: number, total: number) =>
          `显示 ${shown} / ${total} · verdict = keep`,
        sort: {
          "score-desc": "分数 ↓",
          "score-asc": "分数 ↑",
          newest: "最新",
        },
        novelOnly: "仅新主题",
        novelOnlyTitle: "隐藏去重门判定为早前主题重复的条目",
        lastFeed: "最近一次抓取",
        lastFeedTitle: "只显示最近一次“抓取 + 分析”点击产生的条目（5 分钟簇）",
        score: "分数 >= ",
        downloadMd: "下载当前视图为 markdown",
        downloadPdf: "下载当前视图为 PDF",
        backToday: "回到今天",
        backTodayTitle: (today: string) => `回到今天（${today}）`,
      },
      tracker: {
        today: "今天",
        lastFeed: "最近一次抓取",
        lastFeedTitle: "只统计最近一次抓取 + 分析运行产生的条目",
        pulled: "已抓取",
        sources: (count: number) => `${count} 个来源`,
        t1Dropped: "T1 丢弃",
        t1DroppedTitle: "Tier-1 相关性过滤器拒绝的条目",
        t1Kept: "T1 保留",
        t1KeptTitle: "通过 Tier-1 并进入 Tier-2 抓取 + 分析的条目",
        t2Full: "T2 完整",
        t2FullTitle: "Tier-2 成功抓取全文并完成分析",
        fallback: "降级",
        fallbackTitle: "Tier-2 全文抓取失败，降级使用 feed 摘要",
        error: "错误",
        errorTitle: "Tier-2 抓取或分析报错",
        novel: "新主题",
        duplicateShort: "重复",
        histogram: "分数分布 · 0-100",
        histogramTitle: (range: string, count: number) =>
          `${range}: ${count} 条`,
      },
      pullAnalyze: {
        pulled: "已抓取",
        analyzed: "已分析",
        pending: "待补",
        pulling: "抓取中...",
        idle: "抓取 + 分析",
        lastPullTitle:
          "最近一次“抓取 + 分析”点击新增的条目数（0 表示点击生效但没有新条目）",
        analyzedTitle: "最近一次分析簇处理的条目数（5 分钟间隔）",
        drainedTitle:
          "最近一次抓取产生的条目还没有全部分析，重新触发可继续处理",
      },
      progress: {
        analyzing: (done: number, total: number) => `分析中 ${done}/${total}`,
        title: "本次分析已处理的条目数",
      },
      card: {
        readSource: "读原文",
        showLess: "收起",
        expandImpact: "展开影响",
      },
      badges: {
        dedupMissingTitle: "没有记录去重状态",
        duplicate: "重复",
        novel: "新主题",
        contentMissingTitle: "Tier-2 抓取没有运行",
        full: "完整",
        fallback: "降级",
        error: "错误",
      },
      dayGroup: {
        kept: (count: number) => `保留 ${count} 条`,
        median: "中位数",
        noHeadline: "没有标题",
        showing: (top: number, total: number) =>
          `显示前 ${top} 条，共保留 ${total} 条 · 点击打开详情`,
        showAll: (count: number) => `显示全部 ${count} 条 ->`,
      },
      pager: {
        outside: (count: number) =>
          `这个条目不在当前过滤结果中（匹配 ${count} 条）。`,
        notInFilter: (count: number) => `不在过滤结果中 · 匹配 ${count} 条`,
        nextItem: (remaining: number) => `下一条 · 还有 ${remaining} 条待看`,
        last: "已经到最后一条。",
        of: (index: number, total: number) => `${index} / ${total}`,
        left: (count: number) => (count > 0 ? `剩余 ${count} 条` : "最后一条"),
        previousTitle: (title: string) => `上一条 · ${title}`,
        noPrevious: "没有上一条",
        nextTitle: (title: string) => `下一条 · ${title}`,
        next: "下一条",
        noMore: "没有更多条目",
      },
      ingest: {
        idle: "导入",
        pending: "启动中...",
      },
      recap: {
        title: "智能回顾",
        subtitle: "把一段时间的信号聚合成主线",
        verb: "回顾",
        last7: "最近 7 天",
        last30: "最近 30 天",
        custom: "自定义",
        from: "起",
        to: "止",
        generate: "生成回顾",
        regenerate: "重新生成",
        generating: "正在归纳...",
        pending: "启动中...",
        none: "这个区间还没有回顾。",
        empty: "这个区间没有信号通过筛选。",
        badRange: "区间不合法。",
        failed: (message: string) => `回顾失败：${message}`,
        stale: (count: number) => `本次回顾之后又分析了 ${count} 条信号`,
        coverage: (shown: number, considered: number) =>
          `取 ${considered} 条中得分最高的 ${shown} 条归纳`,
        cited: (count: number) => `${count} 条来源`,
        sweptCitation: "来源已过保留期",
        savedTitle: "历史回顾",
        savedSub: "点击任意一条在上方重新打开",
        savedSignals: (count: number) => `${count} 条信号`,
        savedNovel: "新颖",
      },
    },
    knowledge: {
      title: "知识库",
      subtitle: "GBrain wiki · 已入库条目的 ANN 搜索",
      searchPlaceholder: "搜索 wiki（ANN）...",
      clickResult: "点击结果预览。",
      selectDoc: "从目录选择文档，或搜索 wiki。",
      preview: "预览",
      updated: (date: string) => `更新于 ${date}`,
      noMatches: (query: string) => `没有匹配“${query}”。`,
      resultsFor: (count: number, query: string) =>
        `${count} 个结果 · “${query}”`,
      directory: "Wiki 目录",
      review: {
        title: "回顾",
        subtitle: "对已保存文档的间隔重复",
        due: (count: number) => `${count} 篇待回顾`,
        nothingDue: "暂无待回顾的文档。",
        more: (count: number) => `还有 ${count} 篇待回顾`,
        position: (n: number, total: number) => `第 ${n} / ${total} 次回顾`,
        captured: (date: string) => `收录于 ${date}`,
        seen: "已回顾",
        seenPending: "保存中…",
        seenFailed: "保存失败，请重试",
        refresh: "刷新",
        refreshPending: "刷新中…",
        refreshVerb: "回顾刷新",
        refreshStarted: "回顾刷新已启动",
        refreshToastTitle: "正在刷新回顾…",
        refreshToastDescription: "对照 wiki 并生成回顾要点",
        curve: (count: number) => `艾宾浩斯曲线 · ${count} 篇`,
        curveDone: "完成",
        curveDueKey: "待回顾",
        curveScheduledKey: "排期中",
        curveEnrolled: "已入列",
        curveMedian: "中位阶段",
        curveMedianTitle: "处在中间那篇文档正在等的阶段",
        curveDoneStatTitle: "已走完全部阶段，不再排期",
        curveTitle: (stage: string, total: number, due: number) =>
          `${stage}：共 ${total} 篇，${due} 篇待回顾`,
        curveDoneTitle: (total: number) => `已走完全部阶段：${total} 篇`,
      },
      reindex: {
        idle: "重建索引",
        pending: "重建中...",
        toastTitle: "正在重建知识库索引...",
        toastDescription: "重新生成 ANN 向量",
      },
      ingest: {
        heading: "入库链接",
        placeholder: "粘贴 URL 或已暂存文件路径...",
        folderLabel: "文件夹",
        autoClassify: "自动分类",
        submit: "入库",
        submitting: "启动中...",
        started: "入库已启动",
        errorEmpty: "请先输入 URL 或已暂存文件路径",
        activeTitle: "进行中的入库",
        source: { knowledge: "手动", radar: "雷达" },
        steps: {
          fetch: "抓取",
          clean: "清洗",
          enrich: "丰富",
          classify: "分类",
          persist: "写入",
        },
        done: "完成",
        failed: "失败",
        savedTo: (p: string) => `已保存到 ${p}`,
        category: (category: string) => `分类：${category}`,
        indexed: "已索引到 GBrain",
        indexFailed: "GBrain 索引失败",
      },
      manage: {
        newFolder: "新建文件夹",
        newFolderTitle: "新建文件夹",
        newFolderDesc: "在 wiki 下建目录，并登记为入库落点。",
        pathLabel: "路径",
        pathPlaceholder: "例如 investing/quant",
        pathHint: "小写 slug 路径，用 / 分层",
        scopeLabel: "范围说明（可选）",
        scopePlaceholder: "这里放什么——用于辅助自动分类",
        freshnessLabel: "默认时效（可选）",
        freshnessNone: "— 不设 —",
        create: "创建",
        creating: "创建中...",
        folderCreated: (p: string) => `已创建 ${p}`,
        deleteFile: "删除文件",
        deleteFolder: "删除文件夹",
        deleteFileTitle: "删除文件",
        deleteFolderTitle: "删除文件夹",
        deleteFileBody: (name: string) =>
          `删除“${name}”？只删 wiki 文件；GBrain 索引会保留到下次重建索引。`,
        deleteFolderBody: (name: string, count: number) =>
          `删除文件夹“${name}”及其中 ${count} 篇文档？此操作不可恢复。`,
        cancel: "取消",
        confirmDelete: "删除",
        deleting: "删除中...",
        deleted: (name: string) => `已删除 ${name}`,
        errorPath: "请输入文件夹路径",
        errorPathChars: "路径只能包含 a-z、0-9、/、_ 和 -",
        errorExists: "该文件夹已存在",
        errorNotFound: "未找到",
      },
    },
    goals: {
      title: "目标",
      subtitle: (count: number) =>
        `控制 Tier-1 过滤与评分 · 用户状态里的 goals.yaml · ${count} 个目标`,
      missing: "还没有目标文件",
      attention: "goals.yaml 需要处理",
      help: (message: string, path: string) =>
        `${message}。可以在下面添加第一个目标，或从 ${path} 里随包提供的示例开始。`,
      emptyTitle: "没有配置任何目标",
      emptyBody:
        "Tier-1 过滤和 Tier-2 评分都至少需要一个目标。在添加之前分析会直接失败——无人值守的定时运行也一样。",
      startFromExample: "从示例开始",
      viewExamples: "查看示例",
      viewExamplesHint: "随包提供的参考目标，只读",
      fields: {
        name: "name",
        nameHintReadOnly: "slug · 只读",
        nameHintNew: "kebab-case slug",
        description: "description",
        topics: "topics",
        keywords: "keywords",
        addPlaceholder: "添加...",
      },
      removeTitle: (item: string) => `移除 ${item}`,
      deleteConfirm: (name: string) => `删除目标“${name}”？`,
      topicKeywordCount: (topics: number, keywords: number) =>
        `${topics} topic · ${keywords} keyword`,
      edit: "编辑",
      delete: "删除",
      cancel: "取消",
      saveChanges: "保存修改",
      saveGoal: "保存目标",
      addGoal: "添加目标",
      messages: {
        notFound: (name: string) => `找不到目标：${name}`,
        saved: (name: string) => `已保存 ${name}`,
        invalidName: "目标名称必须是 kebab-case",
        exists: (name: string) => `目标已存在：${name}`,
        added: (name: string) => `已添加 ${name}`,
        deleted: (name: string) => `已删除 ${name}`,
        seeded: (count: number) => `已添加 ${count} 个示例目标`,
        seedRefused: "已经配置了目标——先清空，或者逐个添加",
      },
    },
    subscriptions: {
      title: "订阅",
      subtitle: (feeds: number, unread: number) =>
        `只读 · folocli subscription list · ${feeds} 个 feed · ${unread} 未读`,
      loadingSubtitle: "只读 · folocli subscription list",
      loading: "folocli 冷启动，正在获取订阅列表（可能需要 30 秒以上）...",
      unable: "无法加载 Folo 订阅",
      checkAuth: (message: string) =>
        `${message}。用 uv run next-signal doctor 检查 Folo 登录状态。`,
      empty: "Folo 没有返回订阅。",
      all: "全部",
      searchPlaceholder: "搜索 feed...",
      titleColumn: "标题",
      feedUrl: "Feed URL",
      category: "分类",
      unread: "未读",
      noFeedUrl: "没有 feed URL",
      noMatches: (query: string) =>
        `没有 feed 匹配${query ? `“${query}”` : "当前过滤条件"}。`,
    },
    design: {
      title: "设计系统",
      subtitle: "实时设计变量 - 紫色主色 · 会响应导航栏的主题切换",
      tabs: {
        tokens: "变量",
        components: "组件",
        states: "状态",
        brand: "品牌",
      },
    },
    actions: {
      urlMissing: "URL 缺失或格式不正确",
      ingestStarted: "导入已启动",
      analyzeStarted: "分析已启动",
      pullCompleteAnalyzeStarted: "抓取完成，分析已启动",
      analyzeAlreadyRunning: "抓取完成，分析正在进行中",
      reindexStarted: "重建索引已启动",
    },
  },
} as const;

export type Dictionary = (typeof dictionaries)["en"];

export function getDictionary(locale: Locale): Dictionary {
  return dictionaries[locale] as Dictionary;
}

export function isChinese(locale: Locale): boolean {
  return locale === "zh";
}

export function plural(count: number, one: string, many: CountLabel): string {
  return count === 1 ? one : many(count);
}
