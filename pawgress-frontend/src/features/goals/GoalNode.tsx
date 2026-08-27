import { useState } from "react";
import type { Goal, GoalTier, GoalUpdateRequest } from "../../shared/types";
import { GOAL_TIERS } from "../../shared/types";
import { eligibleParents } from "./goalHierarchy";
import type { GoalTreeNode } from "./goalHierarchy";

interface GoalNodeProps {
  node: GoalTreeNode;
  allGoals: Goal[];
  depth: number;
  onUpdate: (goalId: string, patch: GoalUpdateRequest) => void;
  onDelete: (goal: Goal) => void;
  savingId: string | null;
  error: { goalId: string; message: string } | null;
}

/**
 * One row of the V2 goal hierarchy tree (Blueprint §13), plus its children
 * rendered recursively below it. Reuses the same visual language as the
 * existing flat goal list and TaskRow's goal-linking picker, rather than
 * inventing a second UI convention for what's conceptually the same
 * "link this to that" interaction.
 */
export function GoalNode({ node, allGoals, depth, onUpdate, onDelete, savingId, error }: GoalNodeProps) {
  const { goal, children } = node;
  const [pickingParent, setPickingParent] = useState(false);
  const saving = savingId === goal.id;
  const parent = goal.parentGoalId ? allGoals.find((g) => g.id === goal.parentGoalId) ?? null : null;
  const candidates = eligibleParents(goal, allGoals);

  return (
    <li className="goal-node" style={{ marginLeft: depth * 20 }}>
      <div className="goal-node-row">
        <span className="goal-tier-badge">{goal.tier}</span>
        <span className="task-title">{goal.label}</span>

        <select
          className="field-inline field-priority"
          value={goal.tier ?? ""}
          disabled={saving}
          aria-label={`Tier for "${goal.label}"`}
          onChange={(e) => onUpdate(goal.id, { tier: (e.target.value || null) as GoalTier | null })}
        >
          <option value="">No tier</option>
          {GOAL_TIERS.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>

        <span className="field-goal-group">
          {parent ? (
            <button
              type="button"
              className="link"
              disabled={saving}
              onClick={() => onUpdate(goal.id, { parentGoalId: null })}
            >
              under {parent.label} ✕
            </button>
          ) : pickingParent ? (
            <span className="goal-picker" role="group" aria-label={`Set parent for "${goal.label}"`}>
              {candidates.length === 0 ? (
                <span className="muted">
                  {goal.tier ? "No eligible parent yet — give another goal a broader tier first." : "Set a tier first."}
                </span>
              ) : (
                candidates.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    className="link"
                    onClick={() => {
                      onUpdate(goal.id, { parentGoalId: c.id });
                      setPickingParent(false);
                    }}
                  >
                    {c.label} ({c.tier})
                  </button>
                ))
              )}
              <button type="button" className="link" onClick={() => setPickingParent(false)}>
                Cancel
              </button>
            </span>
          ) : (
            <button type="button" className="link" disabled={saving} onClick={() => setPickingParent(true)}>
              Set parent
            </button>
          )}
        </span>

        <button
          type="button"
          className="link task-delete"
          disabled={saving}
          onClick={() => onDelete(goal)}
          aria-label={`Delete "${goal.label}"`}
        >
          Delete
        </button>
      </div>

      {error?.goalId === goal.id && <div className="notice goal-node-error">{error.message}</div>}

      {children.length > 0 && (
        <ul className="goal-tree-children">
          {children.map((child) => (
            <GoalNode
              key={child.goal.id}
              node={child}
              allGoals={allGoals}
              depth={depth + 1}
              onUpdate={onUpdate}
              onDelete={onDelete}
              savingId={savingId}
              error={error}
            />
          ))}
        </ul>
      )}
    </li>
  );
}
