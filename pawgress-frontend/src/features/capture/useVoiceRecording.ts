import { useCallback, useRef, useState } from "react";
import { transcribeAudio, ApiError } from "../../api/client";

/**
 * Voice capture (2026-09-13) — Engineering Handover §4: pulled forward
 * from "someday" specifically because typing is still real friction
 * against the "just talk to it" pitch. Deliberately does NOT auto-submit
 * a capture on transcription success — it hands the transcribed text back
 * to the caller (CaptureForm), which drops it into the same textarea a
 * typed capture would use. A misheard word is then exactly as cheap to
 * fix as a typo, and the user decides when it's ready to submit — same
 * "user owns the resulting structure" principle as AI extraction, applied
 * to transcription instead.
 */

export const VOICE_CAPTURE_SUPPORTED =
  typeof navigator !== "undefined" &&
  typeof navigator.mediaDevices?.getUserMedia === "function" &&
  typeof MediaRecorder !== "undefined";

interface UseVoiceRecordingResult {
  isRecording: boolean;
  isTranscribing: boolean;
  error: string | null;
  startRecording: () => void;
  stopRecording: () => void;
}

export function useVoiceRecording(
  token: string | null,
  onTranscribed: (text: string) => void
): UseVoiceRecordingResult {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = useCallback(async () => {
    setError(null);
    if (!VOICE_CAPTURE_SUPPORTED) {
      setError("Voice capture isn't supported in this browser. You can type instead.");
      return;
    }

    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setError("Couldn't access your microphone — check your browser's permission for this site.");
      return;
    }

    chunksRef.current = [];
    const recorder = new MediaRecorder(stream);

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0) chunksRef.current.push(event.data);
    };

    recorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());
      setIsRecording(false);

      const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
      if (blob.size === 0) return;

      setIsTranscribing(true);
      try {
        const { text } = await transcribeAudio(blob, token!);
        if (text.trim()) {
          onTranscribed(text.trim());
        } else {
          setError("Didn't catch anything in that recording — try again, or type it instead.");
        }
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Couldn't transcribe that recording. You can type it instead.");
      } finally {
        setIsTranscribing(false);
      }
    };

    mediaRecorderRef.current = recorder;
    recorder.start();
    setIsRecording(true);
  }, [token, onTranscribed]);

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop();
  }, []);

  return { isRecording, isTranscribing, error, startRecording, stopRecording };
}
