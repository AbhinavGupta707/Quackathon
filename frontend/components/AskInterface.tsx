"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { askPatientAssistant, askQuery, startGuidedRecovery, voiceQuery } from "@/lib/api";
import { sentenceCase } from "@/lib/format";
import type {
  AfferensState,
  QueryResponse,
  SyncResponse,
  Task,
  TaskResolveResponse,
  TaskVerificationState,
  TaskVerifyResponse
} from "@/lib/types";
import { EvidenceRefs } from "./EvidenceRefs";
import { Panel } from "./Panel";
import { StateBlock } from "./StateBlock";
import { StatusPill } from "./StatusPill";

type AskInterfaceProps = {
  sessionId: string;
  afferensState?: AfferensState;
  mode?: "patient" | "caregiver";
  onAnswered?: (result: QueryResponse) => void | Promise<void>;
  onResolve?: (taskId: string, resolutionNote: string) => Promise<TaskResolveResponse>;
  onSync?: () => Promise<SyncResponse | null | void>;
  onVerify?: (taskId: string) => Promise<TaskVerifyResponse>;
  suggestedQuery?: string;
  tasks?: Task[];
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

type SpeechRecognitionLike = {
  abort: () => void;
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onend: (() => void) | null;
  onerror: ((event: SpeechRecognitionErrorLike) => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionAlternativeLike = {
  transcript: string;
};

type SpeechRecognitionResultLike = {
  0: SpeechRecognitionAlternativeLike;
  isFinal: boolean;
};

type SpeechRecognitionEventLike = {
  resultIndex: number;
  results: {
    length: number;
    [index: number]: SpeechRecognitionResultLike;
  };
};

type SpeechRecognitionErrorLike = {
  error?: string;
};

type BrowserSpeechWindow = Window &
  typeof globalThis & {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };

type QuerySource = "typed" | "voice";

type RecoveryActionState = {
  error?: string;
  loading?: "guidance" | "resolve" | "sync" | "verify";
  message?: string;
  verification?: TaskVerificationState;
};

export function AskInterface({
  sessionId,
  afferensState,
  mode = "caregiver",
  onAnswered,
  onResolve,
  onSync,
  onVerify,
  suggestedQuery = "Where are my keys?",
  tasks = []
}: AskInterfaceProps) {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [resultQuery, setResultQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [listening, setListening] = useState(false);
  const [voiceMessage, setVoiceMessage] = useState<string | null>(null);
  const [voiceEndpointMessage, setVoiceEndpointMessage] = useState<string | null>(null);
  const [speechRecognitionAvailable, setSpeechRecognitionAvailable] = useState(false);
  const [speechSynthesisAvailable, setSpeechSynthesisAvailable] = useState(false);
  const [speakAnswers, setSpeakAnswers] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const transcriptRef = useRef("");
  const submittedTranscriptRef = useRef(false);

  const recoveryTask = useMemo(
    () => tasks.find((task) => task.id === result?.task_id) ?? null,
    [result?.task_id, tasks]
  );

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const speechWindow = window as BrowserSpeechWindow;
    setSpeechRecognitionAvailable(Boolean(speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition));
    setSpeechSynthesisAvailable("speechSynthesis" in window && "SpeechSynthesisUtterance" in window);

    return () => {
      recognitionRef.current?.abort();
      window.speechSynthesis?.cancel();
    };
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmed = query.trim() || suggestedQuery;
    setQuery(trimmed);
    await submitQuery(trimmed, "typed");
  }

  async function submitQuery(trimmed: string, source: QuerySource) {
    if (!trimmed) {
      setError("Enter a question before asking live memory.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    setResultQuery(trimmed);
    setVoiceEndpointMessage(null);

    try {
      const response = isPatientMode
        ? await askPatientAssistant(trimmed, sessionId, source === "voice")
        : source === "voice"
          ? await voiceQuery(trimmed, sessionId, speakAnswers)
          : {
              endpoint: "query_fallback" as const,
              queryResult: await askQuery(trimmed, sessionId),
              spokenText: undefined
            };

      setResult(response.queryResult);
      setVoiceEndpointMessage(response.fallbackReason ?? null);
      await onAnswered?.(response.queryResult);

      if (speakAnswers) {
        speakAnswer(response.spokenText || conciseSpokenAnswer(response.queryResult));
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Query endpoint unavailable.");
    } finally {
      setLoading(false);
    }
  }

  function startListening() {
    if (!speechRecognitionAvailable || typeof window === "undefined") {
      setVoiceMessage("This browser does not expose speech recognition. Typed questions still work.");
      return;
    }

    const speechWindow = window as BrowserSpeechWindow;
    const Recognition = speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setVoiceMessage("This browser does not expose speech recognition. Typed questions still work.");
      return;
    }

    setError(null);
    setVoiceMessage("Listening for one memory question.");
    setVoiceEndpointMessage(null);
    transcriptRef.current = "";
    submittedTranscriptRef.current = false;

    const recognition = new Recognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";
    recognition.onresult = (event) => {
      let interimTranscript = "";
      let finalTranscript = "";

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const transcript = event.results[index][0]?.transcript ?? "";
        if (event.results[index].isFinal) {
          finalTranscript += transcript;
        } else {
          interimTranscript += transcript;
        }
      }

      const transcript = (finalTranscript || interimTranscript).trim();
      if (transcript) {
        transcriptRef.current = transcript;
        setQuery(transcript);
      }

      if (finalTranscript.trim() && !submittedTranscriptRef.current) {
        submittedTranscriptRef.current = true;
        recognition.stop();
        void submitQuery(finalTranscript.trim(), "voice");
      }
    };
    recognition.onerror = (event) => {
      setListening(false);
      const denied = event.error === "not-allowed" || event.error === "service-not-allowed";
      setVoiceMessage(
        denied
          ? "Microphone access was denied. Typed questions still work."
          : "Speech recognition stopped before a transcript was available."
      );
    };
    recognition.onend = () => {
      setListening(false);
      const transcript = transcriptRef.current.trim();
      if (transcript && !submittedTranscriptRef.current) {
        submittedTranscriptRef.current = true;
        void submitQuery(transcript, "voice");
      }
    };

    try {
      recognitionRef.current = recognition;
      recognition.start();
      setListening(true);
    } catch (startError) {
      setListening(false);
      setVoiceMessage(startError instanceof Error ? startError.message : "Speech recognition could not start.");
    }
  }

  function stopListening() {
    recognitionRef.current?.stop();
    setListening(false);
    setVoiceMessage("Stopped listening.");
  }

  function speakAnswer(text: string) {
    if (!speechSynthesisAvailable || typeof window === "undefined") {
      setVoiceMessage("This browser does not expose speech synthesis.");
      return;
    }

    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.96;
    utterance.onend = () => setSpeaking(false);
    utterance.onerror = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.speak(utterance);
  }

  function stopSpeaking() {
    window.speechSynthesis?.cancel();
    setSpeaking(false);
  }

  function toggleSpeakAnswers() {
    setSpeakAnswers((previous) => {
      if (previous) {
        stopSpeaking();
      }
      return !previous;
    });
  }

  const noLiveNode = afferensState && afferensState !== "live";
  const isPatientMode = mode === "patient";

  return (
    <Panel title={isPatientMode ? "What do you need?" : "Ask Memory Guardian"} eyebrow={isPatientMode ? "Speak or type" : "Evidence-Backed Query"}>
      <form className="ask-form" onSubmit={onSubmit}>
        <label htmlFor="guardian-query">{isPatientMode ? "Ask for an item or a little help" : "Question"}</label>
        <div className="ask-form__controls ask-form__controls--voice">
          <input
            id="guardian-query"
            name="query"
            onChange={(event) => setQuery(event.target.value)}
            placeholder={suggestedQuery}
            type="text"
            value={query}
          />
          <button className="button button--primary" disabled={loading} type="submit">
            {loading ? "Checking" : isPatientMode ? "Ask" : "Ask"}
          </button>
          <button
            className="button button--secondary"
            disabled={loading || !speechRecognitionAvailable}
            onClick={listening ? stopListening : startListening}
            title={
              speechRecognitionAvailable
                ? "Transcribe one spoken question in the browser"
                : "Speech recognition is not available in this browser"
            }
            type="button"
          >
            {listening ? "Stop" : "Speak"}
          </button>
        </div>
      </form>

      <div className="voice-control-row" aria-label="Voice answer controls">
        <button
          aria-pressed={speakAnswers}
          className="button button--secondary"
          disabled={!speechSynthesisAvailable}
          onClick={toggleSpeakAnswers}
          title={
            speechSynthesisAvailable
              ? "Toggle spoken answers for future responses"
              : "Speech synthesis is not available in this browser"
          }
          type="button"
        >
          {speakAnswers ? "Voice replies on" : "Voice replies off"}
        </button>
        <button
          className="button button--secondary"
          disabled={!speaking}
          onClick={stopSpeaking}
          type="button"
        >
          Stop reply
        </button>
        {isPatientMode ? null : (
          <>
            <StatusPill
              label={speechRecognitionAvailable ? "Mic supported" : "Mic unsupported"}
              tone={speechRecognitionAvailable ? "good" : "quiet"}
            />
            <StatusPill
              label={speechSynthesisAvailable ? "Speech supported" : "Speech unsupported"}
              tone={speechSynthesisAvailable ? "good" : "quiet"}
            />
          </>
        )}
      </div>

      {voiceMessage ? <StateBlock title={isPatientMode ? "Voice help" : "Voice status"} body={voiceMessage} /> : null}
      {voiceEndpointMessage ? (
        <StateBlock title={isPatientMode ? "Assistant fallback" : "Voice endpoint fallback"} body={voiceEndpointMessage} />
      ) : null}
      {noLiveNode ? (
        <StateBlock
          title={isPatientMode ? "Home memory is waiting" : "No live node for verification"}
          body={
            isPatientMode
              ? "I can still use what I remember, but I need the home camera connection to check the room right now."
              : "Questions can use existing evidence, but guided recovery needs a live Afferens Node before verification can close the task."
          }
        />
      ) : null}
      {error ? <StateBlock tone="error" title={isPatientMode ? "I could not answer yet" : "Query unavailable"} body={error} /> : null}

      {result ? (
        <div className={isPatientMode ? "answer answer--patient" : "answer"}>
          {isPatientMode ? null : (
            <div className="row-heading">
            <StatusPill label={sentenceCase(result.confidence)} tone={result.confidence === "high" ? "good" : "warn"} />
            <StatusPill label={sentenceCase(result.intent)} tone="info" />
            <StatusPill label={result.used_current_perception ? "Current perception" : "No current perception"} tone={result.used_current_perception ? "good" : "quiet"} />
            <StatusPill label={result.used_memory ? "Memory used" : "Memory not used"} tone={result.used_memory ? "info" : "quiet"} />
            <StatusPill label={answerProviderLabel(result.provider)} tone={result.provider === "fireworks" ? "good" : "info"} />
            {result.needs_human_verification ? <StatusPill label="Human verification required" tone="warn" /> : null}
            </div>
          )}
          <p>{result.answer}</p>
          {isPatientMode && result.next_step ? (
            <div className="patient-next-step">
              <span>Next</span>
              <p>{result.next_step}</p>
            </div>
          ) : null}
          {isPatientMode ? (
            result.needs_human_verification ? (
              <p className="disclaimer">Please check important items in person.</p>
            ) : null
          ) : (
            <>
              <dl className="answer-meta">
                <div>
                  <dt>Current perception</dt>
                  <dd>{result.used_current_perception ? "Used" : "Not used"}</dd>
                </div>
                <div>
                  <dt>Memory</dt>
                  <dd>{result.used_memory ? memoryModeLabel(result) : "Not used"}</dd>
                </div>
                <div>
                  <dt>Answer wording</dt>
                  <dd>{answerProviderCopy(result.provider)}</dd>
                </div>
                <div>
                  <dt>Evidence</dt>
                  <dd>
                    <EvidenceRefs ids={answerEvidenceIds(result)} label="Query evidence observations" />
                  </dd>
                </div>
                <div>
                  <dt>Task</dt>
                  <dd>{result.task_id || "No recovery task returned"}</dd>
                </div>
              </dl>
              <p className="disclaimer">
                {result.safety_disclaimer ||
                  "Live Afferens evidence and cited memory are the source of truth. Model wording is assistive and important details still need human verification."}
              </p>
            </>
          )}
          <GuidedRecoveryPanel
            mode={mode}
            onResolve={onResolve}
            onSync={onSync}
            onVerify={onVerify}
            questionText={resultQuery || query}
            queryResult={result}
            sessionId={sessionId}
            task={recoveryTask}
          />
        </div>
      ) : (
        <StateBlock
          title="No answer yet"
          body={
            isPatientMode
              ? `You can speak or type. Try: "${suggestedQuery}"`
              : `Ask with the keyboard or microphone. Try: "${suggestedQuery}"`
          }
        />
      )}
    </Panel>
  );
}

function GuidedRecoveryPanel({
  mode,
  onResolve,
  onSync,
  onVerify,
  questionText,
  queryResult,
  sessionId,
  task
}: {
  mode: "patient" | "caregiver";
  onResolve?: (taskId: string, resolutionNote: string) => Promise<TaskResolveResponse>;
  onSync?: () => Promise<SyncResponse | null | void>;
  onVerify?: (taskId: string) => Promise<TaskVerifyResponse>;
  questionText: string;
  queryResult: QueryResponse;
  sessionId: string;
  task: Task | null;
}) {
  const [actionState, setActionState] = useState<RecoveryActionState>({});
  const [latestTask, setLatestTask] = useState<Task | null>(null);
  const effectiveTask = latestTask ?? task;
  const taskId = effectiveTask?.id ?? queryResult.task_id;

  if (queryResult.intent !== "object_location") {
    return null;
  }

  async function handleStartGuidance() {
    setActionState({ loading: "guidance" });
    try {
      const response = await startGuidedRecovery(questionText || queryResult.answer, sessionId);
      setLatestTask(response.task ?? null);
      setActionState({
        message: response.next_instruction
      });
    } catch (error) {
      setActionState({
        error: error instanceof Error ? error.message : "Guided recovery could not start."
      });
    }
  }

  async function handleSync() {
    if (!onSync) {
      return;
    }

    setActionState({ loading: "sync" });
    try {
      const syncResult = await onSync();
      const observationCount = syncResult?.observations?.length ?? 0;
      setActionState({
        message:
          observationCount > 0
            ? "Live perception synced. Verify the task when the object or target area is in view."
            : "Sync completed, but no new observation was returned. Keep the live node active and try again."
      });
    } catch (error) {
      setActionState({
        error: error instanceof Error ? error.message : "Live perception sync failed."
      });
    }
  }

  async function handleVerify() {
    if (!onVerify || !taskId) {
      return;
    }

    setActionState({ loading: "verify" });
    try {
      const response = await onVerify(taskId);
      setLatestTask(response.task);
      setActionState({
        message: response.verification.message,
        verification: response.verification.state
      });
    } catch (error) {
      setActionState({
        error: error instanceof Error ? error.message : "Live verification failed."
      });
    }
  }

  async function handleResolve() {
    if (!onResolve || !taskId) {
      return;
    }

    setActionState({ loading: "resolve" });
    try {
      const response = await onResolve(taskId, "User reported the object found during guided recovery.");
      setLatestTask(response.task);
      setActionState({
        message: "Human-reported resolution recorded."
      });
    } catch (error) {
      setActionState({
        error: error instanceof Error ? error.message : "Human resolution could not be recorded."
      });
    }
  }

  const closed = effectiveTask?.state === "verified_resolved" || effectiveTask?.state === "dismissed";
  const instruction = recoveryInstruction({
    actionState,
    queryResult,
    task: effectiveTask
  });
  const busy = Boolean(actionState.loading);
  const isPatientMode = mode === "patient";

  return (
    <div className="guided-recovery" aria-label="Guided object recovery">
      <div className="guided-recovery__header">
        <div>
          <p className="eyebrow">{isPatientMode ? "Find it together" : "Guided Recovery"}</p>
          <h3>{isPatientMode ? "I can help you look" : effectiveTask?.title || "Recovery task opened"}</h3>
        </div>
        <StatusPill
          label={isPatientMode ? (closed ? "Found" : "Searching") : effectiveTask?.state ? sentenceCase(effectiveTask.state) : "Task pending"}
          tone={closed ? "good" : actionState.verification === "not_verified" ? "warn" : "info"}
        />
      </div>
      <div className="guided-step">
        <span>{isPatientMode ? "Try" : "Next"}</span>
        <p>{instruction}</p>
      </div>
      <div className="task-actions">
        <button className="button button--secondary" disabled={busy || closed} onClick={() => void handleStartGuidance()} type="button">
          {actionState.loading === "guidance" ? "Starting" : taskId ? (isPatientMode ? "Help again" : "Refresh guidance") : (isPatientMode ? "Help me find it" : "Start guidance")}
        </button>
        {onSync ? (
          <button className="button button--secondary" disabled={busy || closed} onClick={() => void handleSync()} type="button">
            {actionState.loading === "sync" ? "Checking" : isPatientMode ? "Check the room" : "Sync live view"}
          </button>
        ) : null}
        <button className="button button--primary" disabled={busy || !taskId || !onVerify || closed} onClick={() => void handleVerify()} type="button">
          {actionState.loading === "verify" ? "Checking" : isPatientMode ? "I found it" : "Verify task"}
        </button>
        <button className="button button--secondary" disabled={busy || !taskId || !onResolve || closed} onClick={() => void handleResolve()} type="button">
          {actionState.loading === "resolve" ? "Saving" : isPatientMode ? "Mark found" : "Record found"}
        </button>
      </div>
      {actionState.error ? (
        <StateBlock tone="error" title={isPatientMode ? "I could not start looking" : "Guided recovery failed"} body={actionState.error} />
      ) : actionState.message ? (
        <StateBlock
          tone={closed || actionState.verification === "verified" ? "success" : "empty"}
          title={actionState.verification ? (isPatientMode ? "Search update" : `Verification ${sentenceCase(actionState.verification)}`) : isPatientMode ? "Next step" : "Recovery update"}
          body={actionState.message}
        />
      ) : null}
    </div>
  );
}

function recoveryInstruction({
  actionState,
  queryResult,
  task
}: {
  actionState: RecoveryActionState;
  queryResult: QueryResponse;
  task: Task | null;
}): string {
  if (task?.state === "verified_resolved") {
    return "The backend marked this task verified resolved.";
  }

  if (task?.state === "dismissed") {
    return "This task is closed.";
  }

  if (actionState.verification === "verified") {
    return "The live check verified the task. Refresh tasks if the closed state is not visible yet.";
  }

  if (actionState.verification === "not_verified") {
    return "Point the live node at the last-seen area, sync live view, then verify again.";
  }

  if (actionState.verification === "inconclusive") {
    return "Move the live node closer to the likely area, sync live view, then verify again.";
  }

  if (actionState.message) {
    return actionState.message;
  }

  return task?.recommended_action || task?.body || queryResult.answer;
}

function answerProviderLabel(provider?: string | null): string {
  if (provider === "fireworks") {
    return "Fireworks wording";
  }
  if (provider === "deterministic") {
    return "Fallback wording";
  }
  return provider ? sentenceCase(provider) : "Provider not reported";
}

function answerProviderCopy(provider?: string | null): string {
  if (provider === "fireworks") {
    return "Fireworks helped phrase the answer after evidence was selected.";
  }
  if (provider === "deterministic") {
    return "Deterministic fallback wording was used.";
  }
  return "Answer provider was not reported.";
}

function memoryModeLabel(result: QueryResponse): string {
  if (result.intent === "semantic_memory") {
    return "Semantic memory with cited sources";
  }
  if (result.used_current_perception) {
    return "Live Afferens evidence plus memory";
  }
  return "Cited memory";
}

function conciseSpokenAnswer(result: QueryResponse): string {
  const verification = result.needs_human_verification ? " Please verify in person." : "";
  const next = result.next_step ? ` Next step: ${result.next_step}` : "";
  return `${result.answer}${next}${verification}`;
}

function answerEvidenceIds(result: QueryResponse): string[] {
  return result.evidence_ids?.length ? result.evidence_ids : result.evidence_observation_ids;
}
