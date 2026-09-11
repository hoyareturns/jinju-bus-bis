package kr.co.jinjubus.data

import android.content.Context
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kr.co.jinjubus.core.LiveSnapshot
import kr.co.jinjubus.core.RouteSelectionState
import kr.co.jinjubus.core.RouteVariant

private val Context.jinjuBusDataStore by preferencesDataStore(name = "jinju_bus_settings")

class RoutePreferences(
    private val context: Context,
    private val json: Json = BusApi.defaultJson(),
) {
    private object Keys {
        val monitored = stringPreferencesKey("monitored_bus_numbers")
        val focused = stringPreferencesKey("focused_bus_number")
        val cachedLive = stringPreferencesKey("cached_live_response")
        val cachedRoutes = stringPreferencesKey("cached_route_metadata")
    }

    val selection: Flow<RouteSelectionState> = context.jinjuBusDataStore.data.map(::decodeSelection)

    private fun decodeSelection(prefs: Preferences): RouteSelectionState {
        val stored = prefs[Keys.monitored]
        val routes = when {
            stored == null -> null
            stored.isEmpty() -> emptyList()
            else -> stored.split(',').map(String::trim).filter(String::isNotEmpty)
        }
        return RouteSelectionState.fromPersisted(routes, prefs[Keys.focused])
    }

    suspend fun currentSelection(): RouteSelectionState = selection.first()

    suspend fun saveSelection(value: RouteSelectionState) {
        context.jinjuBusDataStore.edit { prefs ->
            prefs[Keys.monitored] = value.monitored.joinToString(",")
            if (value.focused == null) prefs.remove(Keys.focused) else prefs[Keys.focused] = value.focused
        }
    }

    suspend fun saveLive(dto: LiveResponseDto) {
        context.jinjuBusDataStore.edit { prefs ->
            val previous = prefs[Keys.cachedLive]?.let { raw ->
                runCatching { json.decodeFromString<LiveResponseDto>(raw) }.getOrNull()
            }
            prefs[Keys.cachedLive] = json.encodeToString(mergeSuccessfulCache(previous, dto))
        }
    }

    suspend fun loadLive(): LiveSnapshot? {
        val raw = context.jinjuBusDataStore.data.first()[Keys.cachedLive] ?: return null
        return runCatching { json.decodeFromString<LiveResponseDto>(raw).toCore() }.getOrNull()
    }

    suspend fun saveRoutes(dto: RoutesResponseDto) {
        context.jinjuBusDataStore.edit { it[Keys.cachedRoutes] = json.encodeToString(dto) }
    }

    suspend fun loadRoutes(): List<RouteVariant> {
        val raw = context.jinjuBusDataStore.data.first()[Keys.cachedRoutes] ?: return emptyList()
        return runCatching {
            json.decodeFromString<RoutesResponseDto>(raw).routes.map(RouteVariantDto::toCore)
        }.getOrDefault(emptyList())
    }
}
