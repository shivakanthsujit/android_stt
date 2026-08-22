package dev.localflow.dictation.ui

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View
import dev.localflow.dictation.R
import kotlin.math.roundToInt

/** Lightweight, bounded visualization of live microphone amplitude. No samples are persisted. */
class AudioWaveformView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0,
) : View(context, attrs, defStyleAttr) {
    private val levels = FloatArray(BAR_COUNT)
    private val paint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        strokeCap = Paint.Cap.ROUND
    }
    private var active = false
    private var displayedLevel = 0f

    fun setActive(isActive: Boolean) {
        if (active == isActive) return
        active = isActive
        if (!active) {
            levels.fill(0f)
            displayedLevel = 0f
        }
        invalidate()
    }

    fun pushLevel(level: Float) {
        if (!active) return
        displayedLevel += DISPLAY_SMOOTHING * (level.coerceIn(0f, 1f) - displayedLevel)
        val simplifiedLevel = (displayedLevel * DETAIL_STEPS).roundToInt() / DETAIL_STEPS
        levels.copyInto(levels, destinationOffset = 0, startIndex = 1, endIndex = levels.size)
        levels[levels.lastIndex] = simplifiedLevel
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (width <= 0 || height <= 0) return

        val density = resources.displayMetrics.density
        val availableWidth = width - paddingLeft - paddingRight
        val step = availableWidth.toFloat() / BAR_COUNT
        val minimumHeight = 2f * density
        val maximumHeight = (height - paddingTop - paddingBottom).toFloat()
            .coerceAtLeast(minimumHeight) * 0.76f
        val centerY = height / 2f
        paint.strokeWidth = 1.6f * density
        paint.color = context.getColor(
            if (active) R.color.local_flow_recording_wave else R.color.local_flow_outline_strong,
        )

        levels.forEachIndexed { index, level ->
            val displayedLevel = if (active) level else 0f
            val barHeight = minimumHeight + displayedLevel * (maximumHeight - minimumHeight)
            val x = paddingLeft + step / 2f + index * step
            canvas.drawLine(x, centerY - barHeight / 2f, x, centerY + barHeight / 2f, paint)
        }
    }

    private companion object {
        const val BAR_COUNT = 24
        const val DETAIL_STEPS = 5f
        const val DISPLAY_SMOOTHING = 0.42f
    }
}
