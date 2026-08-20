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
}
