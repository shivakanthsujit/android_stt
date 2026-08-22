package dev.localflow.dictation.ui

import android.content.Context
import android.graphics.Canvas
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View
import dev.localflow.dictation.R

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

    fun setActive(isActive: Boolean) {
        if (active == isActive) return
        active = isActive
        if (!active) levels.fill(0f)
        invalidate()
    }

    fun pushLevel(level: Float) {
        if (!active) return
        levels.copyInto(levels, destinationOffset = 0, startIndex = 1, endIndex = levels.size)
        levels[levels.lastIndex] = level.coerceIn(0f, 1f)
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        if (width <= 0 || height <= 0) return

        val density = resources.displayMetrics.density
        val gap = 4f * density
        val availableWidth = width - paddingLeft - paddingRight
        val barWidth = ((availableWidth - gap * (BAR_COUNT - 1)) / BAR_COUNT).coerceAtLeast(2f)
        val minimumHeight = 3f * density
        val maximumHeight = (height - paddingTop - paddingBottom).toFloat()
            .coerceAtLeast(minimumHeight)
        val centerY = height / 2f
        paint.strokeWidth = barWidth
        paint.color = context.getColor(
            if (active) R.color.local_flow_recording else R.color.local_flow_outline_strong,
        )

        levels.forEachIndexed { index, level ->
            val displayedLevel = if (active) level else 0f
            val barHeight = minimumHeight + displayedLevel * (maximumHeight - minimumHeight)
            val x = paddingLeft + barWidth / 2f + index * (barWidth + gap)
            canvas.drawLine(x, centerY - barHeight / 2f, x, centerY + barHeight / 2f, paint)
        }
    }

    private companion object {
        const val BAR_COUNT = 28
    }
}
