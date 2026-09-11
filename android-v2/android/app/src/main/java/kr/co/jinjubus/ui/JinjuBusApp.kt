package kr.co.jinjubus.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import kr.co.jinjubus.MainViewModel

private val JinjuBusColors = lightColorScheme(
    primary = Color(0xFF1D5FD1),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDCE7FF),
    onPrimaryContainer = Color(0xFF08285E),
    secondary = Color(0xFF486284),
    surface = Color(0xFFFAFBFF),
    surfaceVariant = Color(0xFFE7EAF0),
    error = Color(0xFFB3261E),
)

@Composable
fun JinjuBusApp(viewModel: MainViewModel) {
    MaterialTheme(colorScheme = JinjuBusColors) {
        MainScreen(viewModel)
    }
}
