package com.ubat.elibraryai.data

import android.content.Context
import com.google.gson.Gson
import com.google.gson.JsonParser
import com.ubat.elibraryai.BuildConfig
import okhttp3.OkHttpClient
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query
import java.io.IOException
import java.util.concurrent.TimeUnit

// ---- DTOs (match the FastAPI JSON; field names are snake_case on purpose) ----
data class RegisterRequest(val full_name: String, val email: String, val password: String)
data class LoginRequest(val email: String, val password: String)
data class User(val id: Int?, val full_name: String, val email: String?, val role: String)
data class AuthResponse(val access_token: String, val user: User)
data class Book(
    val id: Int, val title: String, val author: String,
    val category: String, val description: String, val license: String,
)
data class BookPage(val total: Int, val items: List<Book>)
data class Category(val name: String, val count: Int)
data class Stats(
    val books: Int, val target_books: Int, val registered_users: Int,
    val guest_download_limit: Int, val user_download_limit: Int,
)
data class MessageResponse(val message: String)

data class MeResponse(
    val id: Int?, val full_name: String, val email: String?, val role: String,
    val download_limit: Int, val downloads_used: Int, val downloads_remaining: Int,
)
data class BookDetail(
    val id: Int, val title: String, val author: String, val category: String, val description: String,
    val license: String, val already_downloaded: Boolean, val downloads_used: Int, val download_limit: Int,
)
data class DownloadResponse(
    val book_id: Int, val title: String, val download_url: String, val already_downloaded: Boolean,
    val downloads_used: Int, val download_limit: Int, val downloads_remaining: Int,
)

interface ApiService {
    @POST("api/auth/register") suspend fun register(@Body body: RegisterRequest): AuthResponse
    @POST("api/auth/login") suspend fun login(@Body body: LoginRequest): AuthResponse
    @POST("api/auth/guest") suspend fun guest(): AuthResponse
    @POST("api/auth/logout") suspend fun logout(): MessageResponse
    @GET("api/auth/me") suspend fun me(): MeResponse
    @GET("api/stats") suspend fun stats(): Stats
    @GET("api/books/{id}") suspend fun bookDetail(@Path("id") id: Int): BookDetail
    @POST("api/books/{id}/download") suspend fun download(@Path("id") id: Int): DownloadResponse
    @GET("api/categories") suspend fun categories(): List<Category>
    @GET("api/books") suspend fun books(
        @Query("q") q: String? = null,
        @Query("category") category: String? = null,
        @Query("page") page: Int = 1,
        @Query("page_size") pageSize: Int = 24,
    ): BookPage
}

/** Stores the JWT + user so the session survives app restarts. */
object Session {
    private lateinit var prefs: android.content.SharedPreferences
    private val gson = Gson()

    fun init(context: Context) {
        prefs = context.getSharedPreferences("session", Context.MODE_PRIVATE)
    }

    val token: String? get() = prefs.getString("token", null)
    val user: User? get() = prefs.getString("user", null)?.let { runCatching { gson.fromJson(it, User::class.java) }.getOrNull() }

    fun save(token: String, user: User) {
        prefs.edit().putString("token", token).putString("user", gson.toJson(user)).apply()
    }

    fun clear() = prefs.edit().clear().apply()
}

object ApiClient {
    val service: ApiService by lazy {
        val client = OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(20, TimeUnit.SECONDS)
            .addInterceptor { chain ->
                val builder = chain.request().newBuilder()
                Session.token?.let { builder.header("Authorization", "Bearer $it") }
                chain.proceed(builder.build())
            }
            .build()
        Retrofit.Builder()
            .baseUrl(BuildConfig.BASE_URL)
            .client(client)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(ApiService::class.java)
    }
}

/** Turns any failure into a short message that is safe to show the user. */
fun errorMessage(e: Throwable): String = when (e) {
    is HttpException -> try {
        val body = e.response()?.errorBody()?.string().orEmpty()
        val detail = JsonParser.parseString(body).asJsonObject.get("detail")
        if (detail.isJsonArray) {
            detail.asJsonArray.joinToString(". ") { it.asJsonObject.get("msg").asString.removePrefix("Value error, ") }
        } else detail.asString
    } catch (_: Exception) {
        "Request failed (${e.code()})"
    }
    is IOException -> "Cannot reach the server. Check your internet connection."
    else -> e.message ?: "Unexpected error"
}
