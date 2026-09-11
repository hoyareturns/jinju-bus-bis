package kr.co.jinjubus.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import kr.co.jinjubus.core.sanitizeRouteNumberInput

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RouteManagementSheet(
    monitored: List<String>,
    onDismiss: () -> Unit,
    onAdd: (String, (String?) -> Unit) -> Unit,
    onDelete: (String) -> Unit,
) {
    var input by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var adding by remember { mutableStateOf(false) }

    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp)
                .padding(bottom = 28.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("표시할 노선", style = MaterialTheme.typography.titleLarge)
            Text(
                "추가된 노선만 실시간 위치를 조회합니다.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            if (monitored.isEmpty()) {
                Text("현재 표시 중인 노선이 없습니다.")
            } else {
                LazyColumn(modifier = Modifier.fillMaxWidth().heightIn(max = 240.dp)) {
                    items(monitored, key = { it }) { busNo ->
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 4.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text("$busNo 번", modifier = Modifier.weight(1f))
                            TextButton(onClick = { onDelete(busNo) }) { Text("삭제") }
                        }
                        HorizontalDivider()
                    }
                }
            }

            OutlinedTextField(
                value = input,
                onValueChange = {
                    input = sanitizeRouteNumberInput(it)
                    error = null
                },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("노선번호") },
                placeholder = { Text("예: 160") },
                singleLine = true,
                isError = error != null,
                supportingText = if (error != null) ({ Text(error.orEmpty()) }) else null,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Ascii),
            )
            Button(
                onClick = {
                    if (input.isBlank()) {
                        error = "노선번호를 입력하세요."
                    } else {
                        adding = true
                        onAdd(input) { message ->
                            adding = false
                            error = message
                            if (message == null) input = ""
                        }
                    }
                },
                enabled = !adding,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (adding) "확인 중…" else "+ 노선 추가")
            }
        }
    }
}
