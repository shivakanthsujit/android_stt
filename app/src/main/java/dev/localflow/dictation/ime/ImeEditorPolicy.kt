package dev.localflow.dictation.ime

import android.text.InputType
import android.view.inputmethod.EditorInfo

data class EditorIdentity(
    val packageName: String?,
    val fieldId: Int,
    val inputType: Int,
)

data class UndoRecord(
    val editor: EditorIdentity,
    val committedText: String,
)

/** Bounded in-memory undo history. Text is still deleted only through [ImeEditorPolicy.canUndo]. */
class ImeUndoHistory(
    private val capacity: Int = DEFAULT_CAPACITY,
) {
    private val records = ArrayDeque<UndoRecord>()

    init {
        require(capacity > 0) { "Undo history capacity must be positive" }
    }

    val size: Int
        get() = records.size

    fun isEmpty(): Boolean = records.isEmpty()

    fun isNotEmpty(): Boolean = records.isNotEmpty()

    fun push(record: UndoRecord) {
        records.addLast(record)
        while (records.size > capacity) records.removeFirst()
    }

    fun lastOrNull(): UndoRecord? = records.lastOrNull()

    fun removeLast(): UndoRecord = records.removeLast()

    fun clear() = records.clear()

    companion object {
        internal const val DEFAULT_CAPACITY = 5
    }
}

/** Pure editor-safety and bounded-undo policy shared by the IME and host unit tests. */
object ImeEditorPolicy {
    fun supportsDictation(inputType: Int): Boolean =
        (inputType and InputType.TYPE_MASK_CLASS) != InputType.TYPE_NULL

    fun isSensitive(inputType: Int, imeOptions: Int): Boolean {
        if (imeOptions and EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING != 0) return true

        val inputClass = inputType and InputType.TYPE_MASK_CLASS
        val variation = inputType and InputType.TYPE_MASK_VARIATION
        return when (inputClass) {
            InputType.TYPE_CLASS_TEXT -> variation in setOf(
                InputType.TYPE_TEXT_VARIATION_PASSWORD,
                InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD,
                InputType.TYPE_TEXT_VARIATION_WEB_PASSWORD,
            )
            InputType.TYPE_CLASS_NUMBER ->
                variation == InputType.TYPE_NUMBER_VARIATION_PASSWORD
            else -> false
        }
    }

    fun canUndo(
        record: UndoRecord?,
        currentEditor: EditorIdentity?,
        textBeforeCursor: CharSequence?,
    ): Boolean = record != null &&
        record.editor == currentEditor &&
        record.committedText.isNotEmpty() &&
        textBeforeCursor?.toString() == record.committedText

    /** Adds only the boundary spaces needed to join a dictation at the current cursor. */
    fun textForCommit(
        dictatedText: String,
        textBeforeCursor: CharSequence?,
        textAfterCursor: CharSequence?,
    ): String {
        if (dictatedText.isEmpty()) return dictatedText

        val prefix = if (needsBoundarySpace(textBeforeCursor?.lastOrNull(), dictatedText.first())) {
            " "
        } else {
            ""
        }
        val suffix = if (needsBoundarySpace(dictatedText.last(), textAfterCursor?.firstOrNull())) {
            " "
        } else {
            ""
        }
        return prefix + dictatedText + suffix
    }

    private fun needsBoundarySpace(left: Char?, right: Char?): Boolean {
        if (left == null || right == null || left.isWhitespace() || right.isWhitespace()) return false
        if (left in OPENING_BOUNDARY_CHARACTERS) return false
        if (right in CLOSING_BOUNDARY_CHARACTERS) return false
        return true
    }

    private val OPENING_BOUNDARY_CHARACTERS = setOf('(', '[', '{', '<', '“', '‘', '"')
    private val CLOSING_BOUNDARY_CHARACTERS = setOf(
        '.', ',', '!', '?', ';', ':', '%', ')', ']', '}', '>', '”', '’', '\'', '"',
    )
}
