import { FormEvent, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Bus,
  ChevronRight,
  Clock,
  Download,
  ExternalLink,
  Footprints,
  History,
  LoaderCircle,
  MapPin,
  Plus,
  Sparkles,
  Navigation,
  Timer,
  X,
} from "lucide-react";
import type { AlternativePlace, ChatResponse, Place } from "./types";
import GoogleMap from "./GoogleMap";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000/api";

const SRC_COLOR: Record<string, string> = {
  reddit: "#d05a2b",
  google_maps: "#3a72c4",
  curated_must_go: "#bd8f33",
  official_open_data: "#bd8f33",
};

const SRC_LABEL: Record<string, string> = {
  reddit: "Reddit · r/travel",
  google_maps: "Google Places",
  curated_must_go: "Curated · France list",
  official_open_data: "Official open data",
};

type ChatMessage =
  | { role: "user"; content: string }
  | { role: "assistant"; content: string; response?: ChatResponse };

type DaySection = { day: number; title: string; summary: string; stops: Place[] };

type RouteSegment = {
  from: Place;
  to: Place;
  distanceKm: number;
  mode: "Walk" | "Metro or bus";
  minutes: number;
};

type SavedSession = {
  id: string;
  title: string;
  timestamp: number;
  messages: ChatMessage[];
  result: ChatResponse;
  planDays: DaySection[];
  planAlts: AlternativePlace[];
};

type MobileTab = "Plan" | "Itinerary" | "Map" | "Route" | "Transit";

function haversineKm(from: Place, to: Place) {
  const R = 6371;
  const dLat = ((to.latitude - from.latitude) * Math.PI) / 180;
  const dLon = ((to.longitude - from.longitude) * Math.PI) / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((from.latitude * Math.PI) / 180) *
      Math.cos((to.latitude * Math.PI) / 180) *
      Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

function buildSegments(stops: Place[]): RouteSegment[] {
  return stops.slice(0, -1).map((from, i) => {
    const to = stops[i + 1];
    const d = haversineKm(from, to);
    const walkable = d <= 1.4;
    return {
      from,
      to,
      distanceKm: d,
      mode: walkable ? "Walk" : "Metro or bus",
      minutes: walkable
        ? Math.max(4, Math.round((d / 4.8) * 60))
        : Math.max(12, Math.round((d / 18) * 60 + 8)),
    };
  });
}

function googleMapsUrl(stop: Place) {
  const q = [stop.name, stop.address, stop.neighborhood, stop.city, "France"]
    .filter(Boolean)
    .join(", ");
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(q)}`;
}

function isMuseumCategory(cat: string) {
  return /museum|musée|gallery|galerie/i.test(cat);
}

const MAPS_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY ?? "";

function placePhotoUrl(photoName: string, maxWidth = 400) {
  if (!photoName || !MAPS_KEY) return "";
  return `https://places.googleapis.com/v1/${photoName}/media?maxWidthPx=${maxWidth}&key=${MAPS_KEY}`;
}

function PlacePhoto({
  photoName,
  alt,
  className = "stop-img",
  style,
}: {
  photoName: string;
  alt?: string;
  className?: string;
  style?: React.CSSProperties;
}) {
  const url = placePhotoUrl(photoName);
  if (!url) return <span className={className} style={style} />;
  return (
    <span className={`${className} has-photo`} style={{ ...style }}>
      <img
        src={url}
        alt={alt ?? ""}
        loading="lazy"
        style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
        onError={(e) => {
          const el = e.currentTarget.parentElement as HTMLElement;
          el.className = className ?? "stop-img";
          e.currentTarget.remove();
        }}
      />
    </span>
  );
}

function Stars({ rating }: { rating: number | null }) {
  if (!rating) return null;
  const full = Math.min(5, Math.floor(rating));
  return (
    <span className="stars">
      {Array.from({ length: full }, (_, i) => (
        <svg key={i} viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2.5l2.9 5.9 6.5.95-4.7 4.58 1.1 6.47L12 17.4l-5.8 3.05 1.1-6.47L2.6 9.35l6.5-.95z" />
        </svg>
      ))}
    </span>
  );
}

function createSessionId() {
  return globalThis.crypto?.randomUUID?.() ?? String(Date.now());
}

function isPermanentlyClosedPlace(place: Place) {
  return (
    place.business_status === "CLOSED_PERMANENTLY" ||
    place.open_status_label.toLowerCase().includes("permanently closed")
  );
}

function withoutClosedStops(days: DaySection[]) {
  return days
    .map((day) => ({ ...day, stops: day.stops.filter((stop) => !isPermanentlyClosedPlace(stop)) }))
    .filter((day) => day.stops.length > 0);
}

function removeNamesFromText(text: string, names: Set<string>) {
  let cleaned = text;
  names.forEach((name) => {
    cleaned = cleaned.replace(new RegExp(name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi"), "");
  });
  return cleaned.replace(/\s{2,}/g, " ").trim();
}

function sanitizeChatResponse(response: ChatResponse): ChatResponse {
  const safeStops = response.itinerary.stops.filter((stop) => !isPermanentlyClosedPlace(stop));
  const safeDays = response.itinerary.days?.length
    ? withoutClosedStops(response.itinerary.days)
    : [];
  const removedNames = new Set(
    response.itinerary.stops
      .filter((stop) => isPermanentlyClosedPlace(stop))
      .map((stop) => stop.name)
  );
  return {
    ...response,
    assistant_message: removeNamesFromText(response.assistant_message, removedNames),
    itinerary: {
      ...response.itinerary,
      stops: safeStops,
      days: safeDays,
    },
    evidence: response.evidence.filter((item) => !removedNames.has(item.place_name)),
  };
}

function sanitizeSavedSession(session: SavedSession): SavedSession {
  const result = sanitizeChatResponse(session.result);
  const planDays = withoutClosedStops(session.planDays);
  return {
    ...session,
    result,
    planDays,
    messages: session.messages.map((msg) =>
      msg.role === "assistant" && msg.response
        ? {
            ...msg,
            content: sanitizeChatResponse(msg.response).assistant_message,
            response: sanitizeChatResponse(msg.response),
          }
        : msg
    ),
  };
}

function loadSessions(): SavedSession[] {
  try {
    return JSON.parse(localStorage.getItem("travelbuddy_sessions") || "[]")
      .map(sanitizeSavedSession)
      .filter((session: SavedSession) => session.result.itinerary.stops.length > 0);
  } catch {
    return [];
  }
}

function persistSessions(sessions: SavedSession[]) {
  localStorage.setItem("travelbuddy_sessions", JSON.stringify(sessions));
}

function altToPlace(alt: AlternativePlace, template: Place): Place {
  return {
    ...template,           // keep photo_name, estimated_duration_minutes, etc.
    name: alt.name,
    category: alt.category,
    city: alt.city,
    neighborhood: "",
    address: "",
    reason: alt.reason,
    local_tip: alt.local_tip,
    tourist_trap_risk: alt.tourist_trap_risk,
    source_url: alt.source_url,
    source_type: "",
    source_title: "",
    latitude: alt.latitude,
    longitude: alt.longitude,
    google_rating: null,
    google_user_rating_count: null,
    google_maps_url: "",
    google_price_label: "",
    google_price_level: "",
    open_status_label: "",
    // photo_name intentionally kept from template — alt has no Google photo
    map_url: "",
    opening_hours: [],
    open_now: null,
    business_status: "",
    confidence: 0,
    price_label: "",
    tags: [],
  };
}

function placeToAlt(place: Place): AlternativePlace {
  return {
    name: place.name,
    category: place.category,
    city: place.city,
    reason: place.reason,
    local_tip: place.local_tip,
    tourist_trap_risk: place.tourist_trap_risk,
    source_url: place.source_url,
    latitude: place.latitude,
    longitude: place.longitude,
  };
}

function normalizeAlternatives(
  alternatives: ChatResponse["alternative_options"] | undefined
): AlternativePlace[] {
  return (alternatives ?? []).map((alternative) =>
    typeof alternative === "string"
      ? {
          name: alternative,
          category: "",
          city: "",
          reason: "",
          local_tip: "",
          tourist_trap_risk: "",
          source_url: "",
          latitude: 0,
          longitude: 0,
        }
      : alternative
  );
}

const WELCOME: ChatMessage = {
  role: "assistant",
  content:
    "Tell me your France city, dates, interests, and what you want to avoid. I'll build a local-first itinerary from real sourced candidates.",
};

export default function App() {
  const [sessionId, setSessionId] = useState<string>(createSessionId);
  const [message, setMessage] = useState(
    "I will be in Paris for 3 days. I love food markets, bookstores, and calm local neighborhoods. Please avoid tourist traps."
  );
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME]);
  const [result, setResult] = useState<ChatResponse | null>(null);
  const [planDays, setPlanDays] = useState<DaySection[]>([]);
  const [planAlts, setPlanAlts] = useState<AlternativePlace[]>([]);
  const [selectedStopIndex, setSelectedStopIndex] = useState(0);
  const [selectedMapDayIndex, setSelectedMapDayIndex] = useState(0);
  const [activeTab, setActiveTab] = useState<"Map" | "Route" | "Transit">("Map");
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState<string | null>(null);
  const [dragReorderOver, setDragReorderOver] = useState<string | null>(null);
  const [draggingStop, setDraggingStop] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const [savedSessions, setSavedSessions] = useState<SavedSession[]>(loadSessions);
  const [mobileTab, setMobileTab] = useState<MobileTab>("Plan");
  const [isMobile, setIsMobile] = useState(() =>
    typeof window !== "undefined" ? window.innerWidth <= 768 : false
  );
  const feedRef = useRef<HTMLDivElement | null>(null);

  const mapDaySections = planDays;

  const activeMapDay =
    mapDaySections[Math.min(selectedMapDayIndex, Math.max(mapDaySections.length - 1, 0))];
  const activeMapStops = activeMapDay?.stops ?? [];
  const selectedStop = activeMapStops[selectedStopIndex] ?? activeMapStops[0] ?? null;
  const segments = buildSegments(activeMapStops);

  const totalWalkMin = segments
    .filter((s) => s.mode === "Walk")
    .reduce((sum, s) => sum + s.minutes, 0);

  const uniqueSources = result
    ? [
        ...new Set(
          result.itinerary.stops
            .map((s) => s.source_type)
            .filter((t) => t && SRC_LABEL[t])
        ),
      ]
    : [];

  const dayStartIndex = 0;

  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    const media = window.matchMedia("(max-width: 768px)");
    const updateViewport = () => setIsMobile(media.matches);
    updateViewport();
    media.addEventListener("change", updateViewport);
    return () => media.removeEventListener("change", updateViewport);
  }, []);

  function saveSession(
    sid: string,
    msgs: ChatMessage[],
    res: ChatResponse,
    days: DaySection[],
    alts: AlternativePlace[]
  ) {
    const safeResponse = sanitizeChatResponse(res);
    const safeDays = withoutClosedStops(days);
    const session: SavedSession = {
      id: sid,
      title: safeResponse.extracted_intent.destination || "Untitled",
      timestamp: Date.now(),
      messages: msgs,
      result: safeResponse,
      planDays: safeDays,
      planAlts: alts,
    };
    setSavedSessions((prev) => {
      const updated = [session, ...prev.filter((s) => s.id !== sid)].slice(0, 20);
      persistSessions(updated);
      return updated;
    });
  }

  function restoreSession(session: SavedSession) {
    const safeSession = sanitizeSavedSession(session);
    setSessionId(session.id);
    setMessages(safeSession.messages);
    setResult(safeSession.result);
    setPlanDays(safeSession.planDays);
    setPlanAlts(safeSession.planAlts);
    setSelectedStopIndex(0);
    setSelectedMapDayIndex(0);
    setError(null);
    setShowHistory(false);
  }

  function deleteSession(sid: string, e: React.MouseEvent) {
    e.stopPropagation();
    setSavedSessions((prev) => {
      const updated = prev.filter((s) => s.id !== sid);
      persistSessions(updated);
      return updated;
    });
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const text = message.trim();
    if (!text) return;

    setLoading(true);
    setError(null);
    setMessages((prev) => [...prev, { role: "user", content: text }]);
    setMessage("");

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          history: messages.map((m) => ({ role: m.role, content: m.content })),
          session_id: sessionId,
        }),
      });
      if (!res.ok) throw new Error("Unable to generate itinerary.");

      const chat = sanitizeChatResponse((await res.json()) as ChatResponse);
      const sid = chat.session_id || sessionId;
      const days: DaySection[] = chat.itinerary.days?.length
        ? chat.itinerary.days
        : [{ day: 1, title: "Day 1", summary: "", stops: chat.itinerary.stops }];
      const alts = normalizeAlternatives(chat.alternative_options);
      setSessionId(sid);
      setResult(chat);
      setPlanDays(days);
      setPlanAlts(alts);
      setSelectedStopIndex(0);
      setSelectedMapDayIndex(0);
      setMessages((prev) => {
        const next = [
          ...prev,
          { role: "assistant" as const, content: chat.assistant_message, response: chat },
        ];
        saveSession(sid, next, chat, days, alts);
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error.");
    } finally {
      setLoading(false);
    }
  }

  function handleNewChat() {
    setSessionId(createSessionId());
    setMessage("");
    setMessages([WELCOME]);
    setResult(null);
    setPlanDays([]);
    setPlanAlts([]);
    setSelectedStopIndex(0);
    setSelectedMapDayIndex(0);
    setError(null);
  }

  async function handleExport() {
    if (!result) return;
    setExporting(true);
    try {
      const res = await fetch(`${API_BASE}/export/pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ itinerary: result.itinerary }),
      });
      if (!res.ok) throw new Error("PDF export failed.");
      const blob = await res.blob();
      window.open(URL.createObjectURL(blob), "_blank", "noopener,noreferrer");
    } catch (err) {
      setError(err instanceof Error ? err.message : "PDF export failed.");
    } finally {
      setExporting(false);
    }
  }

  function handleDrop(alt: AlternativePlace, dayIndex: number, stopIndex: number) {
    const replaced = planDays[dayIndex].stops[stopIndex];
    setPlanDays((prev) => {
      const days = prev.map((d) => ({ ...d, stops: [...d.stops] }));
      days[dayIndex].stops[stopIndex] = altToPlace(alt, days[dayIndex].stops[stopIndex]);
      return days;
    });
    setPlanAlts((prevAlts) => [
      placeToAlt(replaced),
      ...prevAlts.filter((a) => a.name !== alt.name),
    ]);
  }

  function handleStopReorder(fromDay: number, fromStop: number, toDay: number, toStop: number) {
    if (fromDay !== toDay || fromStop === toStop) return;
    setPlanDays((prev) => {
      const days = prev.map((d) => ({ ...d, stops: [...d.stops] }));
      const stops = days[fromDay].stops;
      const [moved] = stops.splice(fromStop, 1);
      stops.splice(toStop, 0, moved);
      return days;
    });
  }

  function handleSelectStop(dayIndex: number, stopIndex: number) {
    setSelectedMapDayIndex(dayIndex);
    setSelectedStopIndex(stopIndex);
  }

  if (isMobile) {
    return (
      <MobileLayout
        activeMapDay={activeMapDay}
        activeMapStops={activeMapStops}
        activeTab={mobileTab}
        error={error}
        exporting={exporting}
        loading={loading}
        mapDaySections={mapDaySections}
        message={message}
        messages={messages}
        onExport={handleExport}
        onMessageChange={setMessage}
        onNewChat={handleNewChat}
        onSelectDay={(index) => {
          setSelectedMapDayIndex(index);
          setSelectedStopIndex(0);
        }}
        onSelectStop={handleSelectStop}
        onSubmit={handleSubmit}
        onTabChange={setMobileTab}
        result={result}
        selectedDayIndex={selectedMapDayIndex}
        selectedStop={selectedStop}
        selectedStopIndex={selectedStopIndex}
        totalWalkMin={totalWalkMin}
        uniqueSources={uniqueSources}
      />
    );
  }

  return (
    <div className="app">
      {/* ── Col 1: Chat ── */}
      <aside className="col chat">
        <header className="chat-top">
          <div className="brand">
            <span className="brand-mark" />
            <div>
              <div className="brand-name">TravelBuddy</div>
              <div className="brand-sub">France</div>
              <div className="tricolore">
                <i /><i /><i />
              </div>
            </div>
          </div>
          <div style={{ display: "flex", gap: 6 }}>
            <button
              className="icon-btn"
              type="button"
              onClick={() => setShowHistory((v) => !v)}
              title="Session history"
            >
              <History size={13} />
            </button>
            <button className="icon-btn" type="button" onClick={handleNewChat} disabled={loading}>
              <Plus size={13} />
              New trip
            </button>
          </div>
        </header>

        {/* History panel */}
        {showHistory && (
          <div className="history-panel scroll">
            <div className="hist-head">
              <span className="eyebrow">Recent sessions</span>
              <button className="icon-btn" style={{ height: 26, padding: "0 8px" }} onClick={() => setShowHistory(false)}>
                <X size={12} />
              </button>
            </div>
            {savedSessions.length === 0 ? (
              <div className="hist-empty">No saved sessions yet</div>
            ) : (
              savedSessions.map((sess) => (
                <button
                  key={sess.id}
                  className={`hist-session${sess.id === sessionId ? " active" : ""}`}
                  type="button"
                  onClick={() => restoreSession(sess)}
                >
                  <span className="hist-title">{sess.title}</span>
                  <span className="hist-meta">
                    {new Date(sess.timestamp).toLocaleDateString("en-GB", {
                      day: "numeric", month: "short", year: "numeric",
                    })}
                    {" · "}
                    {sess.planDays.reduce((n, d) => n + d.stops.length, 0)} stops
                  </span>
                  <button
                    className="hist-del"
                    type="button"
                    onClick={(e) => deleteSession(sess.id, e)}
                    title="Delete"
                  >
                    <X size={10} />
                  </button>
                </button>
              ))
            )}
          </div>
        )}

        <div className="chat-feed scroll" ref={feedRef}>
          {messages.map((msg, i) => (
            <div className={`msg ${msg.role === "user" ? "user" : "ai"}`} key={i}>
              <div className="msg-role">
                <span className={`avatar ${msg.role === "user" ? "user" : "ai"}`}>
                  {msg.role === "user" ? "Y" : "A"}
                </span>
                <span className="msg-name">{msg.role === "user" ? "You" : "Arthur"}</span>
              </div>
              <div className="bubble">
                {msg.content}
                {"response" in msg && msg.response && (
                  <>
                    <div className="src-row">
                      {[
                        ...new Set(
                          msg.response.itinerary.stops
                            .map((s) => s.source_type)
                            .filter((t) => SRC_LABEL[t])
                        ),
                      ].map((type) => (
                        <span className="src-chip" key={type}>
                          <span className="src-dot" style={{ background: SRC_COLOR[type] }} />
                          {SRC_LABEL[type]}
                        </span>
                      ))}
                    </div>
                    <div className="ai-action">
                      <Sparkles size={13} />
                      {msg.response.itinerary.stops.length} stops ·{" "}
                      {msg.response.extracted_intent.duration_days} days ·{" "}
                      {msg.response.extracted_intent.pace || "mixed"} pace
                    </div>
                  </>
                )}
              </div>
            </div>
          ))}
          {loading && (
            <div className="msg ai">
              <div className="msg-role">
                <span className="avatar ai">A</span>
                <span className="msg-name">Arthur</span>
              </div>
              <div className="bubble" style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <LoaderCircle size={14} className="spin" style={{ color: "var(--green)" }} />
              </div>
            </div>
          )}
        </div>

        <footer className="chat-input">
          <div className="input-wrap">
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder='Refine your plan — e.g. "more street food stops", "fewer museums"…'
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                  e.preventDefault();
                  handleSubmit(e as unknown as FormEvent);
                }
              }}
            />
            <button className="send-btn" type="button" onClick={handleSubmit} disabled={loading}>
              {loading ? <LoaderCircle size={14} className="spin" /> : "Generate plan"}
              <ArrowRight size={14} />
            </button>
          </div>
          {error && <div className="error-note">{error}</div>}
        </footer>
      </aside>

      {/* ── Col 2: Plan ── */}
      <main className="col plan scroll">
        <div className="plan-inner">
          {result ? (
            <>
              <section className="summary">
                <div className="summary-head">
                  <div>
                    <div className="eyebrow" style={{ marginBottom: 10 }}>Votre itinéraire</div>
                    <h1>{result.extracted_intent.destination}</h1>
                    <div className="loc-sub">
                      <span>France</span>
                      <span className="dotsep" />
                      <span>{result.extracted_intent.duration_days} days</span>
                      <span className="dotsep" />
                      <span>Built from your sources</span>
                    </div>
                  </div>
                  <button
                    className="export-btn"
                    type="button"
                    onClick={handleExport}
                    disabled={exporting}
                  >
                    {exporting ? <LoaderCircle size={14} className="spin" /> : <Download size={14} />}
                    Export PDF
                  </button>
                </div>

                <p className="summary-lead">{result.itinerary.summary}</p>

                <div className="meta-strip">
                  <div className="meta">
                    <div className="meta-val">{result.itinerary.stops.length}</div>
                    <div className="meta-lbl">Stops</div>
                  </div>
                  <div className="meta">
                    <div className="meta-val">
                      {totalWalkMin}
                      <span>min</span>
                    </div>
                    <div className="meta-lbl">Walking</div>
                  </div>
                  <div className="meta">
                    <div className="meta-val">
                      {uniqueSources.length}
                      <span>sources</span>
                    </div>
                    <div className="meta-lbl">Verified from</div>
                  </div>
                  <div className="meta">
                    <div className="meta-val">
                      {result.extracted_intent.duration_days}
                      <span>days</span>
                    </div>
                    <div className="meta-lbl">Duration</div>
                  </div>
                </div>
              </section>

              <div className="tagrow">
                {result.itinerary.themes.map((t) => (
                  <span className="tag" key={t}>
                    <span className="tdot" />
                    {t}
                  </span>
                ))}
                {result.extracted_intent.avoid.map((a) => (
                  <span className="tag neg" key={a}>
                    <span className="tdot" />
                    Avoid {a}
                  </span>
                ))}
              </div>

              <div className="days">
                {mapDaySections.map((day, dayIndex) => {
                  const daySegments = buildSegments(day.stops);
                  return (
                    <section key={`${day.day}-${day.title}`}>
                      <div className="day-head">
                        <span className="day-no">Jour {day.day}</span>
                        <span className="day-title">{day.title || `Day ${day.day}`}</span>
                        <span className="day-sub">{day.stops.length} stops</span>
                      </div>
                      <div className="stop-list">
                        {day.stops.map((stop, stopIndex) => {
                          const isActive =
                            dayIndex === selectedMapDayIndex && stopIndex === selectedStopIndex;
                          const seg = daySegments[stopIndex];
                          const dropKey = `${dayIndex}-${stopIndex}`;
                          return (
                            <button
                              key={`${stop.name}-${stopIndex}`}
                              className={`stop${isActive ? " active" : ""}${dragOver === dropKey ? " drag-over" : ""}${dragReorderOver === dropKey ? " drag-over-reorder" : ""}${draggingStop === dropKey ? " stop-dragging" : ""}`}
                              type="button"
                              draggable
                              onClick={() => handleSelectStop(dayIndex, stopIndex)}
                              onDragStart={(e) => {
                                setDraggingStop(dropKey);
                                e.dataTransfer.setData("application/stop", JSON.stringify({ dayIndex, stopIndex }));
                                e.dataTransfer.effectAllowed = "move";
                              }}
                              onDragEnd={() => {
                                setDraggingStop(null);
                                setDragReorderOver(null);
                              }}
                              onDragOver={(e) => {
                                e.preventDefault();
                                if (e.dataTransfer.types.includes("application/stop")) {
                                  setDragReorderOver(dropKey);
                                } else {
                                  setDragOver(dropKey);
                                }
                              }}
                              onDragLeave={() => { setDragOver(null); setDragReorderOver(null); }}
                              onDrop={(e) => {
                                e.preventDefault();
                                setDragOver(null);
                                setDragReorderOver(null);
                                setDraggingStop(null);
                                const stopData = e.dataTransfer.getData("application/stop");
                                if (stopData) {
                                  try {
                                    const { dayIndex: fd, stopIndex: fs } = JSON.parse(stopData);
                                    handleStopReorder(fd, fs, dayIndex, stopIndex);
                                  } catch {}
                                } else {
                                  try {
                                    const alt: AlternativePlace = JSON.parse(e.dataTransfer.getData("text/plain"));
                                    handleDrop(alt, dayIndex, stopIndex);
                                  } catch {}
                                }
                              }}
                            >
                              <span className="stop-num">{stopIndex + 1}</span>
                              <PlacePhoto photoName={stop.photo_name} alt={stop.name} className="stop-img" />
                              <span className="stop-body">
                                <span className="stop-cat">
                                  <span
                                    className={`cat-chip${isMuseumCategory(stop.category) ? " museum" : ""}`}
                                  >
                                    {stop.category || "Place"}
                                  </span>
                                </span>
                                <span className="stop-name">{stop.name}</span>
                                <span className="stop-meta">
                                  {stop.google_rating && (
                                    <span className="mini">
                                      <Stars rating={stop.google_rating} />
                                      <span className="rating-num">{stop.google_rating.toFixed(1)}</span>
                                    </span>
                                  )}
                                  {stop.open_status_label && (
                                    <span className="mini">
                                      <Clock size={12} />
                                      {stop.open_status_label.split(" ").slice(0, 3).join(" ")}
                                    </span>
                                  )}
                                  {stop.source_url ? (
                                    <a
                                      className="src-link"
                                      href={stop.source_url}
                                      target="_blank"
                                      rel="noreferrer"
                                      style={{ color: SRC_COLOR[stop.source_type] ?? "var(--ink-3)" }}
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      <ExternalLink size={11} />
                                      {SRC_LABEL[stop.source_type] ?? stop.source_type}
                                    </a>
                                  ) : (
                                    <span
                                      className="src-link"
                                      style={{ color: SRC_COLOR[stop.source_type] ?? "var(--ink-3)" }}
                                    >
                                      <ExternalLink size={11} />
                                      {SRC_LABEL[stop.source_type] ?? stop.source_type}
                                    </span>
                                  )}
                                </span>
                              </span>
                              <span className="stop-right">
                                {seg ? (
                                  <span className="walkpill">
                                    {seg.mode === "Walk" ? <Footprints size={11} /> : <Bus size={11} />}
                                    {seg.minutes} min
                                  </span>
                                ) : (
                                  <span />
                                )}
                                <span className="chev">
                                  <ChevronRight size={15} />
                                </span>
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    </section>
                  );
                })}
              </div>

              {planAlts.length > 0 && (
                <section className="alts">
                  <div className="alts-head">
                    <h3>Alternative places</h3>
                    <span className="hint">Drag cards to swap · drag ⠿ handle to reorder</span>
                  </div>
                  <div className="alts-grid">
                    {planAlts.slice(0, 4).map((alt, idx) => (
                      <div
                        className="alt"
                        key={`${alt.name}-${alt.city}-${idx}`}
                        draggable
                        onDragStart={(e) => {
                          e.dataTransfer.setData("text/plain", JSON.stringify(alt));
                          e.dataTransfer.effectAllowed = "move";
                        }}
                      >
                        <span className="alt-img alt-drag-handle" title="Drag to swap" />
                        <span className="alt-body">
                          <span className={`cat-chip${isMuseumCategory(alt.category) ? " museum" : ""}`}>
                            {alt.category || "Place"}
                          </span>
                          <span className="alt-name">{alt.name}</span>
                          {alt.reason && <span className="alt-reason">{alt.reason}</span>}
                        </span>
                        <span className="drag-hint">
                          ↕ drag
                        </span>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </>
          ) : (
            <div className="plan-empty">
              <MapPin size={32} />
              <h2>Your itinerary appears here</h2>
              <p>Start a conversation to generate a local-first France plan.</p>
            </div>
          )}
        </div>
      </main>

      {/* ── Col 3: Map ── */}
      <aside className="col mapcol">
        <div className="map-tabs">
          {(["Map", "Route", "Transit"] as const).map((tab) => (
            <button
              key={tab}
              className={`map-tab${activeTab === tab ? " active" : ""}`}
              type="button"
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
          <span className="spacer" />
          <span className="map-legend">
            <span className="legend-line" />
            Your route
          </span>
        </div>

        {activeTab === "Map" && (
          <>
            {mapDaySections.length > 1 && (
              <div style={{ display: "flex", gap: 6, padding: "10px 16px 0", flexWrap: "wrap" }}>
                {mapDaySections.map((day, index) => (
                  <button
                    key={`${day.day}-${day.title}`}
                    className={`map-tab${selectedMapDayIndex === index ? " active" : ""}`}
                    type="button"
                    onClick={() => {
                      setSelectedMapDayIndex(index);
                      setSelectedStopIndex(0);
                    }}
                  >
                    Day {day.day}
                  </button>
                ))}
              </div>
            )}

            <div className="map-embed">
              <GoogleMap
                stops={activeMapStops}
                selectedIndex={selectedStopIndex}
                onSelectStop={setSelectedStopIndex}
                startIndex={dayStartIndex}
              />
            </div>

            <div className="detail">
              {selectedStop ? (
                <>
                  <div className={`detail-img${selectedStop.photo_name ? " has-photo" : ""}`}>
                    {selectedStop.photo_name ? (
                      <img
                        src={placePhotoUrl(selectedStop.photo_name, 600)}
                        alt={selectedStop.name}
                        style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                        onError={(e) => { e.currentTarget.style.display = "none"; }}
                      />
                    ) : null}
                    <span className="detail-stop-no">{selectedStopIndex + 1}</span>
                  </div>
                  <div className="detail-cat">
                    <span className={`cat-chip${isMuseumCategory(selectedStop.category) ? " museum" : ""}`}>
                      {selectedStop.category || "Place"}
                    </span>
                  </div>
                  <div className="detail-top">
                    <div style={{ flex: 1 }}>
                      <div className="detail-name">{selectedStop.name}</div>
                      <div className="detail-sub">
                        {selectedStop.neighborhood || selectedStop.city}
                      </div>
                    </div>
                    {selectedStop.google_rating && (
                      <div className="detail-meta">
                        <Stars rating={selectedStop.google_rating} />
                        <span className="rate-num">{selectedStop.google_rating.toFixed(1)}</span>
                      </div>
                    )}
                  </div>
                  {(selectedStop.local_tip || selectedStop.reason) && (
                    <div className="detail-why">
                      <div className="why-lbl">
                        <span className="eyebrow">Why it's here</span>
                      </div>
                      <div className="why-quote">
                        {selectedStop.local_tip || selectedStop.reason}
                      </div>
                    </div>
                  )}
                  <div className="detail-foot">
                    {segments[selectedStopIndex] ? (
                      <span className="walkpill">
                        {segments[selectedStopIndex].mode === "Walk" ? (
                          <Footprints size={11} />
                        ) : (
                          <Bus size={11} />
                        )}
                        {segments[selectedStopIndex].minutes} min to next
                      </span>
                    ) : (
                      <span style={{ fontSize: 11, color: "var(--ink-4)", fontFamily: "var(--mono)" }}>
                        Last stop
                      </span>
                    )}
                    <a
                      className="openbtn"
                      href={selectedStop.source_url || googleMapsUrl(selectedStop)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <ExternalLink size={12} />
                      Open source
                    </a>
                  </div>
                </>
              ) : (
                <div className="detail-empty">Select a stop to see details</div>
              )}
            </div>

            <div className="legs scroll">
              {segments.length > 0 ? (
                <>
                  <div className="legs-head">
                    <span className="eyebrow">Between stops</span>
                  </div>
                  {segments.map((seg, i) => (
                    <div
                      key={`${seg.from.name}-${seg.to.name}`}
                      className={`leg${i === selectedStopIndex ? " hl" : ""}`}
                    >
                      <span className="leg-route">
                        <span className="leg-no">{i + 1}</span>
                        <span className="leg-arrow">
                          <ArrowRight size={11} />
                        </span>
                        <span className="leg-no">{i + 2}</span>
                      </span>
                      <span className="leg-mode">
                        {seg.mode === "Walk" ? <Footprints size={13} /> : <Bus size={13} />}
                        {seg.mode === "Walk" ? "Walk" : "Metro + walk"}
                      </span>
                      <span className="leg-time">
                        {seg.minutes}
                        <span> min</span>
                      </span>
                    </div>
                  ))}
                </>
              ) : (
                <div style={{ padding: "18px 4px", fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--ink-4)", textAlign: "center" }}>
                  Route appears after plan is generated
                </div>
              )}
            </div>
          </>
        )}

        {activeTab === "Route" && (
          <RoutePanel days={mapDaySections} />
        )}

        {activeTab === "Transit" && (
          <TransitPanel days={mapDaySections} />
        )}
      </aside>
    </div>
  );
}

type MobileLayoutProps = {
  activeMapDay: DaySection | undefined;
  activeMapStops: Place[];
  activeTab: MobileTab;
  error: string | null;
  exporting: boolean;
  loading: boolean;
  mapDaySections: DaySection[];
  message: string;
  messages: ChatMessage[];
  onExport: () => void;
  onMessageChange: (message: string) => void;
  onNewChat: () => void;
  onSelectDay: (index: number) => void;
  onSelectStop: (dayIndex: number, stopIndex: number) => void;
  onSubmit: (event: FormEvent) => void;
  onTabChange: (tab: MobileTab) => void;
  result: ChatResponse | null;
  selectedDayIndex: number;
  selectedStop: Place | null;
  selectedStopIndex: number;
  totalWalkMin: number;
  uniqueSources: string[];
};

function MobileLayout({
  activeMapDay,
  activeMapStops,
  activeTab,
  error,
  exporting,
  loading,
  mapDaySections,
  message,
  messages,
  onExport,
  onMessageChange,
  onNewChat,
  onSelectDay,
  onSelectStop,
  onSubmit,
  onTabChange,
  result,
  selectedDayIndex,
  selectedStop,
  selectedStopIndex,
  totalWalkMin,
  uniqueSources,
}: MobileLayoutProps) {
  const segments = buildSegments(activeMapStops);
  const tabs: MobileTab[] = ["Plan", "Itinerary", "Map", "Route", "Transit"];

  return (
    <div className={`mobile-app mobile-tab-${activeTab.toLowerCase()}`}>
      <header className="mobile-topbar">
        <div className="brand">
          <span className="brand-mark" />
          <div>
            <div className="brand-name">TravelBuddy</div>
            <div className="brand-sub">France</div>
          </div>
        </div>
        <button className="icon-btn" type="button" onClick={onNewChat} disabled={loading}>
          <Plus size={13} />
          New trip
        </button>
      </header>

      <section className="mobile-map-stage" aria-label="Travel route map">
        <GoogleMap
          stops={activeMapStops}
          selectedIndex={selectedStopIndex}
          onSelectStop={(index) => onSelectStop(selectedDayIndex, index)}
          startIndex={0}
        />
        {mapDaySections.length > 1 && (
          <div className="mobile-day-tabs" aria-label="Itinerary days">
            {mapDaySections.map((day, index) => (
              <button
                className={selectedDayIndex === index ? "active" : ""}
                key={`${day.day}-${day.title}`}
                type="button"
                onClick={() => onSelectDay(index)}
              >
                Day {day.day}
              </button>
            ))}
          </div>
        )}
      </section>

      <main className="mobile-sheet">
        <div className="mobile-sheet-handle" />
        <div className="mobile-sheet-scroll scroll">
          {activeTab === "Plan" && (
            <section className="mobile-plan">
              <div className="mobile-section-heading">
                <div>
                  <span className="eyebrow">Plan</span>
                  <h1>Plan your France trip</h1>
                </div>
              </div>
              <div className="mobile-chat-feed">
                {messages.map((chatMessage, index) => (
                  <div
                    className={`msg ${chatMessage.role === "user" ? "user" : "ai"}`}
                    key={`${chatMessage.role}-${index}`}
                  >
                    <div className="msg-role">
                      <span className={`avatar ${chatMessage.role === "user" ? "user" : "ai"}`}>
                        {chatMessage.role === "user" ? "Y" : "A"}
                      </span>
                      <span className="msg-name">
                        {chatMessage.role === "user" ? "You" : "Arthur"}
                      </span>
                    </div>
                    <div className="bubble">{chatMessage.content}</div>
                  </div>
                ))}
                {loading && (
                  <div className="msg ai">
                    <div className="msg-role">
                      <span className="avatar ai">A</span>
                      <span className="msg-name">Arthur</span>
                    </div>
                    <div className="bubble mobile-loading">
                      <LoaderCircle size={14} className="spin" />
                      Planning your trip
                    </div>
                  </div>
                )}
              </div>
              <form className="mobile-composer" onSubmit={onSubmit}>
                <textarea
                  value={message}
                  onChange={(event) => onMessageChange(event.target.value)}
                  placeholder='Refine your plan — e.g. "more street food stops"'
                  rows={4}
                />
                <button className="send-btn" type="submit" disabled={loading}>
                  {loading ? <LoaderCircle size={14} className="spin" /> : "Generate plan"}
                  <ArrowRight size={14} />
                </button>
              </form>
              {error && <div className="error-note mobile-error">{error}</div>}
            </section>
          )}

          {activeTab === "Itinerary" && (
            <section className="mobile-itinerary">
              {result ? (
                <>
                  <div className="mobile-section-heading mobile-itinerary-heading">
                    <div>
                      <span className="eyebrow">Votre itinéraire</span>
                      <h1>{result.extracted_intent.destination}</h1>
                      <div className="loc-sub">
                        France · {result.extracted_intent.duration_days} days
                      </div>
                    </div>
                    <button
                      className="export-btn mobile-export"
                      type="button"
                      onClick={onExport}
                      disabled={exporting}
                    >
                      {exporting ? <LoaderCircle size={14} className="spin" /> : <Download size={14} />}
                      PDF
                    </button>
                  </div>
                  <p className="summary-lead">{result.itinerary.summary}</p>
                  <div className="mobile-meta-strip">
                    <div><strong>{result.itinerary.stops.length}</strong><span>Stops</span></div>
                    <div><strong>{totalWalkMin}</strong><span>Walk min</span></div>
                    <div><strong>{uniqueSources.length}</strong><span>Sources</span></div>
                    <div><strong>{result.extracted_intent.duration_days}</strong><span>Days</span></div>
                  </div>
                  <div className="tagrow mobile-tagrow">
                    {result.itinerary.themes.map((theme) => (
                      <span className="tag" key={theme}><span className="tdot" />{theme}</span>
                    ))}
                    {result.extracted_intent.avoid.map((item) => (
                      <span className="tag neg" key={item}><span className="tdot" />Avoid {item}</span>
                    ))}
                  </div>
                  <div className="mobile-days">
                    {mapDaySections.map((day, dayIndex) => {
                      const daySegments = buildSegments(day.stops);
                      return (
                        <section key={`${day.day}-${day.title}`}>
                          <div className="day-head">
                            <span className="day-no">Jour {day.day}</span>
                            <span className="day-title">{day.title || `Day ${day.day}`}</span>
                            <span className="day-sub">{day.stops.length} stops</span>
                          </div>
                          <div className="stop-list">
                            {day.stops.map((stop, stopIndex) => {
                              const segment = daySegments[stopIndex];
                              const active =
                                dayIndex === selectedDayIndex && stopIndex === selectedStopIndex;
                              return (
                                <button
                                  className={`stop mobile-stop${active ? " active" : ""}`}
                                  key={`${day.day}-${stop.name}-${stopIndex}`}
                                  type="button"
                                  onClick={() => onSelectStop(dayIndex, stopIndex)}
                                >
                                  <span className="stop-num">{stopIndex + 1}</span>
                                  <PlacePhoto photoName={stop.photo_name} alt={stop.name} className="stop-img" />
                                  <span className="stop-body">
                                    <span className="cat-chip">{stop.category || "Place"}</span>
                                    <span className="stop-name">{stop.name}</span>
                                    <span className="stop-meta">
                                      {stop.open_status_label || stop.neighborhood || stop.city}
                                    </span>
                                  </span>
                                  <span className="stop-right">
                                    {segment && (
                                      <span className="walkpill">
                                        {segment.mode === "Walk" ? <Footprints size={11} /> : <Bus size={11} />}
                                        {segment.minutes} min
                                      </span>
                                    )}
                                    <ChevronRight size={15} />
                                  </span>
                                </button>
                              );
                            })}
                          </div>
                        </section>
                      );
                    })}
                  </div>
                </>
              ) : (
                <div className="mobile-empty">
                  <MapPin size={28} />
                  <h2>Your itinerary appears here</h2>
                  <p>Start a conversation to generate a local-first France plan.</p>
                  <button className="send-btn" type="button" onClick={() => onTabChange("Plan")}>
                    Open Plan
                    <ArrowRight size={14} />
                  </button>
                </div>
              )}
            </section>
          )}

          {activeTab === "Map" && (
            <section className="mobile-map-content">
              <div className="mobile-section-heading">
                <div>
                  <span className="eyebrow">Map</span>
                  <h1>{activeMapDay?.title || "Route map"}</h1>
                </div>
              </div>
              {selectedStop ? (
                <div className="mobile-place-detail">
                  <PlacePhoto
                    photoName={selectedStop.photo_name}
                    alt={selectedStop.name}
                    className="detail-img"
                  />
                  <span className="cat-chip">{selectedStop.category || "Place"}</span>
                  <h2>{selectedStop.name}</h2>
                  <p>{selectedStop.neighborhood || selectedStop.city}</p>
                  {(selectedStop.local_tip || selectedStop.reason) && (
                    <blockquote>{selectedStop.local_tip || selectedStop.reason}</blockquote>
                  )}
                  <div className="detail-foot">
                    {segments[selectedStopIndex] ? (
                      <span className="walkpill">
                        {segments[selectedStopIndex].mode === "Walk" ? <Footprints size={11} /> : <Bus size={11} />}
                        {segments[selectedStopIndex].minutes} min to next
                      </span>
                    ) : <span className="eyebrow">Last stop</span>}
                    <a
                      className="openbtn"
                      href={selectedStop.source_url || googleMapsUrl(selectedStop)}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <ExternalLink size={12} />
                      Open source
                    </a>
                  </div>
                </div>
              ) : (
                <div className="mobile-empty compact">
                  <MapPin size={26} />
                  <h2>Select a stop to see details</h2>
                  <p>Generate a plan from the Plan tab to draw your route.</p>
                </div>
              )}
            </section>
          )}

          {activeTab === "Route" && <RoutePanel days={mapDaySections} />}
          {activeTab === "Transit" && <TransitPanel days={mapDaySections} />}
        </div>
      </main>

      <nav className="mobile-bottom-nav" aria-label="TravelBuddy sections">
        {tabs.map((tab) => (
          <button
            className={activeTab === tab ? "active" : ""}
            key={tab}
            type="button"
            onClick={() => onTabChange(tab)}
          >
            {tab}
          </button>
        ))}
      </nav>
    </div>
  );
}

// ─── Route tab ────────────────────────────────────────────────────────────────

type DaySection2 = { day: number; title: string; summary: string; stops: Place[] };

function RoutePanel({ days }: { days: DaySection2[] }) {
  if (!days.length) {
    return (
      <div className="tab-panel scroll tab-empty">
        <Navigation size={28} />
        <p>Generate a plan to see the full route breakdown.</p>
      </div>
    );
  }

  const allSegs = days.map((day) => ({ day, segs: buildSegments(day.stops) }));
  const totalWalk = allSegs
    .flatMap((d) => d.segs)
    .filter((s) => s.mode === "Walk")
    .reduce((sum, s) => sum + s.minutes, 0);
  const totalTransit = allSegs
    .flatMap((d) => d.segs)
    .filter((s) => s.mode !== "Walk").length;
  const totalKm = allSegs
    .flatMap((d) => d.segs)
    .reduce((sum, s) => sum + s.distanceKm, 0);

  return (
    <div className="tab-panel scroll">
      <div className="route-summary">
        <div className="route-stat">
          <span className="route-stat-val">{totalWalk}<span>min</span></span>
          <span className="route-stat-lbl">Walking</span>
        </div>
        <div className="route-stat">
          <span className="route-stat-val">{totalKm.toFixed(1)}<span>km</span></span>
          <span className="route-stat-lbl">Total distance</span>
        </div>
        <div className="route-stat">
          <span className="route-stat-val">{totalTransit}<span>hops</span></span>
          <span className="route-stat-lbl">Metro / bus</span>
        </div>
      </div>

      {allSegs.map(({ day, segs }) => (
        <div className="route-day" key={day.day}>
          <div className="route-day-head">
            <span className="day-no" style={{ fontSize: 9, padding: "4px 8px" }}>
              Jour {day.day}
            </span>
            <span style={{ fontFamily: "var(--sans)", fontSize: 16, fontWeight: 600 }}>
              {day.title || `Day ${day.day}`}
            </span>
            <span style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--ink-3)", marginLeft: "auto" }}>
              {day.stops.length} stops
            </span>
          </div>

          {segs.length === 0 && (
            <div style={{ fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--ink-4)", padding: "8px 0" }}>
              Single stop — no segments
            </div>
          )}

          {segs.map((seg, i) => (
            <div className="route-seg" key={`${seg.from.name}-${i}`}>
              <div className="route-seg-names">
                <span className="route-seg-from">{seg.from.name}</span>
                <ArrowRight size={10} style={{ color: "var(--ink-4)", flexShrink: 0 }} />
                <span className="route-seg-to">{seg.to.name}</span>
              </div>
              <div className="route-seg-meta">
                <span className="walkpill" style={{ fontSize: 10 }}>
                  {seg.mode === "Walk" ? <Footprints size={10} /> : <Bus size={10} />}
                  {seg.mode === "Walk" ? "Walk" : "Metro + walk"}
                </span>
                <span style={{ fontFamily: "var(--mono)", fontSize: 10.5, color: "var(--ink-3)" }}>
                  {seg.distanceKm.toFixed(2)} km
                </span>
                <span style={{ fontFamily: "var(--mono)", fontSize: 10.5, fontWeight: 600, color: "var(--ink)" }}>
                  {seg.minutes} min
                </span>
              </div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

// ─── Transit tab ──────────────────────────────────────────────────────────────

function toHHMM(minutesFromMidnight: number) {
  const h = Math.floor(minutesFromMidnight / 60) % 24;
  const m = minutesFromMidnight % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function TransitPanel({ days }: { days: DaySection2[] }) {
  if (!days.length) {
    return (
      <div className="tab-panel scroll tab-empty">
        <Timer size={28} />
        <p>Generate a plan to see the estimated day schedule.</p>
      </div>
    );
  }

  return (
    <div className="tab-panel scroll">
      {days.map((day) => {
        const segs = buildSegments(day.stops);
        let clock = 9 * 60;

        return (
          <div className="transit-day" key={day.day}>
            <div className="route-day-head">
              <span className="day-no" style={{ fontSize: 9, padding: "4px 8px" }}>
                Jour {day.day}
              </span>
              <span style={{ fontFamily: "var(--sans)", fontSize: 16, fontWeight: 600 }}>
                {day.title || `Day ${day.day}`}
              </span>
            </div>

            <div className="timeline">
              {day.stops.map((stop, i) => {
                const arrivalTime = clock;
                const stayMin = stop.estimated_duration_minutes || 60;
                const departTime = arrivalTime + stayMin;
                const seg = segs[i];
                clock = departTime + (seg?.minutes ?? 0);

                return (
                  <div key={`${stop.name}-${i}`}>
                    <div className="tl-stop">
                      <div className="tl-time">{toHHMM(arrivalTime)}</div>
                      <div className="tl-dot-col">
                        <div className="tl-dot" />
                        {(seg || i < day.stops.length - 1) && <div className="tl-line" />}
                      </div>
                      <div className="tl-body">
                        <div className="tl-name">{stop.name}</div>
                        <div className="tl-meta">
                          <span className={`cat-chip${isMuseumCategory(stop.category) ? " museum" : ""}`}
                            style={{ fontSize: 10, height: 18, padding: "0 6px" }}>
                            {stop.category || "Place"}
                          </span>
                          <span style={{ fontFamily: "var(--mono)", fontSize: 10, color: "var(--ink-3)" }}>
                            {stayMin} min stay · depart {toHHMM(departTime)}
                          </span>
                        </div>
                      </div>
                    </div>

                    {seg && (
                      <div className="tl-leg">
                        <div className="tl-time tl-time-sm">{toHHMM(departTime)}</div>
                        <div className="tl-dot-col">
                          <div className="tl-leg-icon">
                            {seg.mode === "Walk" ? <Footprints size={10} /> : <Bus size={10} />}
                          </div>
                          <div className="tl-line" />
                        </div>
                        <div className="tl-leg-desc">
                          {seg.mode === "Walk" ? "Walk" : "Metro or bus"} · {seg.distanceKm.toFixed(2)} km · {seg.minutes} min
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}

              {day.stops.length > 0 && (
                <div className="tl-stop tl-end">
                  <div className="tl-time">{toHHMM(clock)}</div>
                  <div className="tl-dot-col">
                    <div className="tl-dot tl-dot-end" />
                  </div>
                  <div className="tl-body" style={{ color: "var(--ink-3)", fontSize: 12 }}>
                    End of day {day.day}
                  </div>
                </div>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
