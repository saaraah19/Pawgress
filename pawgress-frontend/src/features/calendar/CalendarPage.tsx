import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../auth/AuthContext";
import { getCalendarStatus, startCalendarOAuth, listCalendarEvents, disconnectCalendar } from "../../api/client";
import { CALENDAR_STATUS_QUERY_KEY, CALENDAR_EVENTS_QUERY_KEY } from "../../shared/queryKeys";
import type { CalendarEvent } from "../../shared/types";

function formatDayHeading(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" });
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

function dayKey(iso: string): string {
  return new Date(iso).toDateString();
}

function groupEventsByDay(events: CalendarEvent[]): { key: string; heading: string; events: CalendarEvent[] }[] {
  const groups = new Map<string, CalendarEvent[]>();
  for (const event of events) {
    const key = dayKey(event.start);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(event);
  }
  return Array.from(groups.entries()).map(([key, dayEvents]) => ({
    key,
    heading: formatDayHeading(dayEvents[0].start),
    events: dayEvents,
  }));
}

/**
 * V2 Calendar (Blueprint §13), read-only v1 — explicit scope decision,
 * 2026-08-19: Google Calendar -> Pawgress only. This page answers one
 * question, plainly: "what's already happening in my life?" No
 * productivity overlays, no task/goal/habit tie-ins, no AI summaries, no
 * companion reactions, no analytics. Just the events, grouped by day.
 */
export function CalendarPage() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const statusQuery = useQuery({
    queryKey: CALENDAR_STATUS_QUERY_KEY,
    queryFn: () => getCalendarStatus(token!),
    enabled: !!token,
  });

  const eventsQuery = useQuery({
    queryKey: CALENDAR_EVENTS_QUERY_KEY,
    queryFn: () => listCalendarEvents(token!),
    enabled: !!token && statusQuery.data?.connected === true,
  });

  const connectMutation = useMutation({
    mutationFn: () => startCalendarOAuth(token!),
    onSuccess: (data) => {
      window.location.href = data.authorizationUrl;
    },
  });

  const disconnectMutation = useMutation({
    mutationFn: () => disconnectCalendar(token!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: CALENDAR_STATUS_QUERY_KEY });
      queryClient.invalidateQueries({ queryKey: CALENDAR_EVENTS_QUERY_KEY });
    },
  });

  // Google redirects back here with ?connected=1 after a successful
  // connect (calendar_integration/routes.py's oauth_callback). Just
  // re-fetch status and clear the query param — no banner, no
  // celebratory copy, matching the rest of the app's restraint.
  useEffect(() => {
    if (searchParams.get("connected") === "1") {
      queryClient.invalidateQueries({ queryKey: CALENDAR_STATUS_QUERY_KEY });
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, setSearchParams, queryClient]);

  const dayGroups = eventsQuery.data ? groupEventsByDay(eventsQuery.data) : [];

  return (
    <div className="page calendar-page">
      <div className="card calendar-card">
        <h1>Calendar</h1>

        {statusQuery.isLoading && <p className="muted">Loading...</p>}

        {statusQuery.data && !statusQuery.data.connected && (
          <>
            <p className="muted">
              Connect your Google Calendar to see what's already on it, right here.
            </p>
            <button className="primary" onClick={() => connectMutation.mutate()} disabled={connectMutation.isPending}>
              {connectMutation.isPending ? "Connecting..." : "Connect Google Calendar"}
            </button>
            {connectMutation.isError && (
              <div className="notice">Couldn't start that just now. Try again in a moment.</div>
            )}
          </>
        )}

        {statusQuery.data?.connected && (
          <>
            <div className="calendar-connection-row">
              <span className="muted">
                {statusQuery.data.accountEmail ? `Connected as ${statusQuery.data.accountEmail}` : "Connected"}
              </span>
              <button
                type="button"
                className="link"
                onClick={() => disconnectMutation.mutate()}
                disabled={disconnectMutation.isPending}
              >
                Disconnect
              </button>
            </div>

            {eventsQuery.isLoading && <p className="muted">Loading your calendar...</p>}

            {eventsQuery.isError && (
              <div className="notice">
                Couldn't reach Google Calendar just now.{" "}
                <button className="link" onClick={() => eventsQuery.refetch()}>
                  Try again
                </button>
              </div>
            )}

            {eventsQuery.data && dayGroups.length === 0 && (
              <p className="empty-state">Nothing on your calendar for the next two weeks.</p>
            )}

            {dayGroups.length > 0 && (
              <div className="calendar-agenda">
                {dayGroups.map((group) => (
                  <div key={group.key} className="calendar-day-group">
                    <p className="calendar-day-heading">{group.heading}</p>
                    <ul className="calendar-event-list">
                      {group.events.map((event) => (
                        <li key={event.id} className="calendar-event-row">
                          <span className="calendar-event-time">
                            {event.allDay ? "All day" : formatTime(event.start)}
                          </span>
                          <span className="calendar-event-title">{event.title}</span>
                          {event.location && <span className="calendar-event-location">{event.location}</span>}
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
