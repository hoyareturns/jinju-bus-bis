package kr.co.jinjubus.data

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.CancellationException
import kr.co.jinjubus.core.MainUiState
import kr.co.jinjubus.core.RouteSelectionState
import kr.co.jinjubus.core.RouteValidationDecision
import kr.co.jinjubus.core.applyCachedSnapshot
import kr.co.jinjubus.core.applyLiveSnapshot
import kr.co.jinjubus.core.applyLocalBootstrap
import kr.co.jinjubus.core.applyRefreshFailure
import kr.co.jinjubus.core.applyRefreshStarted
import kr.co.jinjubus.core.applyRouteMetadata
import kr.co.jinjubus.core.mergeRouteMetadataWithErrors
import kr.co.jinjubus.core.applySelection
import kr.co.jinjubus.core.decideRouteValidation

class BusRepository(
    private val preferences: RoutePreferences,
    private val api: BusApi,
    private val snapshotStore: RouteSnapshotStore,
) {
    private val refreshMutex = Mutex()
    private val selectionMutex = Mutex()
    private val _state = MutableStateFlow(MainUiState())
    val state: StateFlow<MainUiState> = _state.asStateFlow()

    fun setForeground(active: Boolean) = api.setForeground(active)

    suspend fun initialize() {
        selectionMutex.withLock {
        val selection = preferences.currentSelection()
        val landmarks = snapshotStore.landmarks()
        val localVariants = snapshotStore.routeVariants(selection.monitored)
        var next = applySelection(_state.value, selection)
        next = applyLocalBootstrap(next, landmarks, localVariants)

        val cachedRoutes = preferences.loadRoutes().filter { it.busNo in selection.monitored }
        if (cachedRoutes.isNotEmpty()) next = applyRouteMetadata(next, cachedRoutes)
        preferences.loadLive()?.let { cached -> next = applyCachedSnapshot(next, cached) }
        _state.value = next
        api.setMonitoredBusNumbers(selection.monitored)
        }

        if (_state.value.monitoredBusNumbers.isNotEmpty()) {
            refreshMetadata()
            refreshLive()
        }
    }

    suspend fun refreshLive() = refreshMutex.withLock {
        val monitored = _state.value.monitoredBusNumbers
        if (monitored.isEmpty()) {
            _state.value = _state.value.copy(isRefreshing = false, routeErrors = emptyList())
            return@withLock
        }
        _state.value = applyRefreshStarted(_state.value)
        try {
            val dto = api.locations(monitored)
            val snapshot = dto.toCore()
            if (dto.routes.any { it.status == "ok" }) preferences.saveLive(dto)
            _state.value = applyLiveSnapshot(_state.value, snapshot)
        } catch (cancelled: CancellationException) {
            _state.value = _state.value.copy(isRefreshing = false)
            throw cancelled
        } catch (_: Exception) {
            _state.value = applyRefreshFailure(_state.value)
        }
    }

    suspend fun refreshMetadata() {
        val monitored = _state.value.monitoredBusNumbers
        if (monitored.isEmpty()) return
        runCatching { api.routes(monitored) }.onFailure { if (it is CancellationException) throw it }
            .onSuccess { dto ->
                if (dto.errors.isEmpty()) preferences.saveRoutes(dto)
                _state.value = mergeRouteMetadataWithErrors(
                    _state.value,
                    requestedBusNumbers = monitored.filter { it in _state.value.monitoredBusNumbers },
                    variants = dto.routes.map(RouteVariantDto::toCore),
                    errors = dto.errors.map(RouteErrorDto::toCore),
                )
            }
    }

    suspend fun addRoute(rawBusNo: String): String? {
        val busNo = rawBusNo.trim()
        if (busNo.isEmpty()) return "노선번호를 입력하세요."
        if (busNo in _state.value.monitoredBusNumbers) {
            focusRoute(busNo)
            return null
        }

        val localExists = snapshotStore.containsBusNumber(busNo)
        val remoteResult = runCatching { api.routes(listOf(busNo)) }
            .onFailure { if (it is CancellationException) throw it }
        val remote = remoteResult.getOrNull()
        when (
            decideRouteValidation(
                localExists = localExists,
                remoteSucceeded = remoteResult.isSuccess,
                remoteHasRoutes = remote?.routes?.isNotEmpty() == true,
                remoteConfirmsUnknown = remote?.errors?.any {
                    it.busNo == busNo && it.routeId == null && it.message == "노선 정보 없음"
                } == true,
            )
        ) {
            RouteValidationDecision.REJECT_UNKNOWN ->
                return remote?.errors?.firstOrNull()?.message ?: "진주 노선 정보를 찾을 수 없습니다."
            RouteValidationDecision.REJECT_UNAVAILABLE ->
                return "노선을 확인할 수 없습니다. 네트워크 상태를 확인하세요."
            RouteValidationDecision.ACCEPT,
            RouteValidationDecision.ACCEPT_OFFLINE_SNAPSHOT -> Unit
        }

        val localVariants = snapshotStore.routeVariants(listOf(busNo))
        selectionMutex.withLock {
        val current = RouteSelectionState(
            monitored = _state.value.monitoredBusNumbers,
            focused = _state.value.focusedBusNumber,
        )
        val nextSelection = current.add(busNo).focus(busNo)
        api.setMonitoredBusNumbers(nextSelection.monitored)
        var next = applySelection(_state.value, nextSelection)
        if (localVariants.isNotEmpty()) next = applyRouteMetadata(next, localVariants)
        remote?.let { dto ->
            next = mergeRouteMetadataWithErrors(
                next,
                requestedBusNumbers = listOf(busNo),
                variants = dto.routes.map(RouteVariantDto::toCore),
                errors = dto.errors.map(RouteErrorDto::toCore),
            )
        }
        _state.value = next
        preferences.saveSelection(nextSelection)
        }

        refreshMetadata()
        refreshLive()
        return null
    }

    suspend fun removeRoute(busNo: String) {
        selectionMutex.withLock {
        val current = RouteSelectionState(
            monitored = _state.value.monitoredBusNumbers,
            focused = _state.value.focusedBusNumber,
        )
        val nextSelection = current.remove(busNo)
        _state.value = applySelection(_state.value, nextSelection).copy(isRefreshing = false)
        api.setMonitoredBusNumbers(nextSelection.monitored)
        preferences.saveSelection(nextSelection)
        }
        if (_state.value.monitoredBusNumbers.isNotEmpty()) refreshLive()
    }

    suspend fun focusRoute(busNo: String) = selectionMutex.withLock {
        val current = RouteSelectionState(
            monitored = _state.value.monitoredBusNumbers,
            focused = _state.value.focusedBusNumber,
        )
        val next = current.focus(busNo)
        if (next == current) return@withLock
        _state.value = applySelection(_state.value, next)
        preferences.saveSelection(next)
    }
}
