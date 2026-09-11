package kr.co.jinjubus.ui

import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kr.co.jinjubus.MainViewModel
import kr.co.jinjubus.core.freshnessText

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun MainScreen(viewModel: MainViewModel) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val lifecycleOwner = LocalLifecycleOwner.current
    var showManager by remember { mutableStateOf(false) }
    var pendingDelete by remember { mutableStateOf<String?>(null) }

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> viewModel.startForegroundPolling()
                Lifecycle.Event.ON_STOP -> viewModel.stopForegroundPolling()
                else -> Unit
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            viewModel.stopForegroundPolling()
        }
    }

    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.surface) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .statusBarsPadding()
                .navigationBarsPadding()
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(Modifier.weight(1f)) {
                    Text("진주 버스", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Text(
                        if (state.fetchedAt == null && state.routeErrors.isNotEmpty()) {
                            "실시간 정보 조회 실패"
                        } else freshnessText(state.fetchedAt, state.isUsingStaleData),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                OutlinedButton(onClick = viewModel::refresh, enabled = !state.isRefreshing) {
                    Text(if (state.isRefreshing) "갱신 중" else "↻ 갱신")
                }
            }

            BusMap(
                vehicles = state.vehiclesByStableVehicleKey.values.toList(),
                landmarks = state.landmarks,
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(0.47f),
            )

            HorizontalDivider()
            LazyRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                items(state.monitoredBusNumbers, key = { it }) { busNo ->
                    val selected = state.focusedBusNumber == busNo
                    Surface(
                        modifier = Modifier.combinedClickable(
                            onClick = { viewModel.focusRoute(busNo) },
                            onLongClick = { pendingDelete = busNo },
                        ),
                        shape = MaterialTheme.shapes.large,
                        color = if (selected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant,
                    ) {
                        Text(
                            busNo,
                            modifier = Modifier.padding(horizontal = 16.dp, vertical = 9.dp),
                            fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
                        )
                    }
                }
                item {
                    Button(onClick = { showManager = true }) { Text("+") }
                }
            }

            RouteDetailPanel(
                state = state,
                onAddRoute = { showManager = true },
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(0.53f),
            )
        }
    }

    if (showManager) {
        RouteManagementSheet(
            monitored = state.monitoredBusNumbers,
            onDismiss = { showManager = false },
            onAdd = viewModel::addRoute,
            onDelete = viewModel::removeRoute,
        )
    }

    pendingDelete?.let { busNo ->
        AlertDialog(
            onDismissRequest = { pendingDelete = null },
            title = { Text("$busNo 번을 삭제할까요?") },
            text = { Text("삭제하면 이 노선의 실시간 위치 조회도 즉시 중단됩니다.") },
            confirmButton = {
                TextButton(onClick = {
                    pendingDelete = null
                    viewModel.removeRoute(busNo)
                }) { Text("삭제") }
            },
            dismissButton = { TextButton(onClick = { pendingDelete = null }) { Text("취소") } },
        )
    }
}
