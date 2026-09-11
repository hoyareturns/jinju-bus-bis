package kr.co.jinjubus

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kr.co.jinjubus.data.BusApi
import kr.co.jinjubus.data.BusRepository
import kr.co.jinjubus.data.RoutePreferences
import kr.co.jinjubus.data.RouteSnapshotStore

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = BusRepository(
        preferences = RoutePreferences(application),
        api = BusApi(BuildConfig.TAGO_API_KEY, log = { android.util.Log.i("TAGO", it) }),
        snapshotStore = RouteSnapshotStore(application),
    )
    val state = repository.state

    private val initialized = AtomicBoolean(false)
    private var pollJob: Job? = null

    fun initialize() {
        if (!initialized.compareAndSet(false, true)) return
        viewModelScope.launch { repository.initialize() }
    }

    fun startForegroundPolling() {
        repository.setForeground(true)
        if (pollJob?.isActive == true) return
        pollJob = viewModelScope.launch {
            while (isActive) {
                delay(15_000)
                repository.refreshLive()
            }
        }
    }

    fun stopForegroundPolling() {
        repository.setForeground(false)
        pollJob?.cancel()
        pollJob = null
    }

    fun refresh() {
        viewModelScope.launch { repository.refreshLive() }
    }

    fun focusRoute(busNo: String) {
        viewModelScope.launch { repository.focusRoute(busNo) }
    }

    fun addRoute(busNo: String, onResult: (String?) -> Unit) {
        viewModelScope.launch { onResult(repository.addRoute(busNo)) }
    }

    fun removeRoute(busNo: String) {
        viewModelScope.launch { repository.removeRoute(busNo) }
    }
}
