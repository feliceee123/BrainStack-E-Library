package com.ubat.elibraryai.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val Maroon = Color(0xFF7A0019)
val MaroonDark = Color(0xFF5A0012)
val Blush = Color(0xFFF3E7E5)

@Composable
fun ELibraryTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = lightColorScheme(
            primary = Maroon,
            onPrimary = Color.White,
            secondary = MaroonDark,
            primaryContainer = Blush,
            onPrimaryContainer = Maroon,
            background = Color(0xFFFAF6F5),
            surface = Color.White,
        ),
        content = content,
    )
}
