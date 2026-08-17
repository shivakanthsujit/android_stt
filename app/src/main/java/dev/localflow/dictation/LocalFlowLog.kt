package dev.localflow.dictation

import android.util.Log

object LocalFlowLog {
    private const val TAG = "LocalFlow"

    fun debug(message: String) = Log.d(TAG, message)

    fun info(message: String) = Log.i(TAG, message)

    fun error(message: String, throwable: Throwable? = null) =
        Log.e(TAG, message, throwable)
}
