package com.ubat.elibraryai

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.ubat.elibraryai.data.ApiClient
import com.ubat.elibraryai.data.AuthResponse
import com.ubat.elibraryai.data.LoginRequest
import com.ubat.elibraryai.data.RegisterRequest
import com.ubat.elibraryai.data.ResendVerificationRequest
import com.ubat.elibraryai.data.Session
import com.ubat.elibraryai.data.User
import com.ubat.elibraryai.data.errorMessage
import kotlinx.coroutines.launch

/** Holds the signed-in user and handles register / login / guest / logout. */
class AppViewModel : ViewModel() {
    var user by mutableStateOf<User?>(if (Session.token != null) Session.user else null)
        private set
    var loading by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    var notice by mutableStateOf<String?>(null)
        private set

    private val api get() = ApiClient.service

    fun clearError() { error = null; notice = null }

    fun login(email: String, password: String) =
        authenticate { api.login(LoginRequest(email.trim(), password)) }

    fun register(name: String, email: String, password: String) {
        viewModelScope.launch {
            loading = true
            error = null
            notice = null
            try {
                notice = api.register(RegisterRequest(name.trim(), email.trim(), password)).message
            } catch (e: Exception) {
                error = errorMessage(e)
            }
            loading = false
        }
    }

    fun resendVerification(email: String) {
        viewModelScope.launch {
            loading = true
            error = null
            notice = null
            try {
                notice = api.resendVerification(ResendVerificationRequest(email.trim())).message
            } catch (e: Exception) {
                error = errorMessage(e)
            }
            loading = false
        }
    }

    fun continueAsGuest() = authenticate { api.guest() }

    fun logout() {
        viewModelScope.launch {
            try { api.logout() } catch (_: Exception) { /* token may already be invalid */ }
            Session.clear()
            user = null
        }
    }

    private fun authenticate(call: suspend () -> AuthResponse) {
        viewModelScope.launch {
            loading = true
            error = null
            notice = null
            try {
                val res = call()
                Session.save(res.access_token, res.user)
                user = res.user
            } catch (e: Exception) {
                error = errorMessage(e)
            }
            loading = false
        }
    }
}
