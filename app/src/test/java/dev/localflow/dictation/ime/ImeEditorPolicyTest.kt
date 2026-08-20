package dev.localflow.dictation.ime

import android.text.InputType
import android.view.inputmethod.EditorInfo
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ImeEditorPolicyTest {
    @Test
    fun passwordAndPrivateEditorsAreSensitive() {
        val textPasswords = listOf(
            InputType.TYPE_TEXT_VARIATION_PASSWORD,
            InputType.TYPE_TEXT_VARIATION_VISIBLE_PASSWORD,
            InputType.TYPE_TEXT_VARIATION_WEB_PASSWORD,
        )
        textPasswords.forEach { variation ->
            assertTrue(
                ImeEditorPolicy.isSensitive(
                    InputType.TYPE_CLASS_TEXT or variation,
                    imeOptions = 0,
                ),
            )
        }
        assertTrue(
            ImeEditorPolicy.isSensitive(
                InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_VARIATION_PASSWORD,
                imeOptions = 0,
            ),
        )
        assertTrue(
            ImeEditorPolicy.isSensitive(
                InputType.TYPE_CLASS_TEXT,
                EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING,
            ),
        )
    }

    @Test
    fun ordinaryTextAndPhoneEditorsRemainAvailable() {
        assertFalse(
            ImeEditorPolicy.isSensitive(
                InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_LONG_MESSAGE,
                imeOptions = 0,
            ),
        )
        assertFalse(
            ImeEditorPolicy.isSensitive(InputType.TYPE_CLASS_PHONE, imeOptions = 0),
        )
        assertTrue(ImeEditorPolicy.supportsDictation(InputType.TYPE_CLASS_TEXT))
        assertFalse(ImeEditorPolicy.supportsDictation(InputType.TYPE_NULL))
    }

    @Test
    fun undoRequiresSameEditorAndExactImmediateSuffix() {
        val editor = EditorIdentity("dev.example.notes", 12, InputType.TYPE_CLASS_TEXT)
        val record = UndoRecord(editor, "Hello there")

        assertTrue(ImeEditorPolicy.canUndo(record, editor, "Hello there"))
        assertFalse(ImeEditorPolicy.canUndo(record, editor.copy(fieldId = 13), "Hello there"))
        assertFalse(ImeEditorPolicy.canUndo(record, editor, "edited there"))
        assertFalse(ImeEditorPolicy.canUndo(null, editor, "Hello there"))
    }
}
