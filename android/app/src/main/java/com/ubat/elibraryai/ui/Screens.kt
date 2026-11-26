@file:OptIn(ExperimentalMaterial3Api::class)

package com.ubat.elibraryai.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Face
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.ubat.elibraryai.AppViewModel
import com.ubat.elibraryai.data.ApiClient
import com.ubat.elibraryai.data.Book
import com.ubat.elibraryai.data.BookDetail
import com.ubat.elibraryai.data.MeResponse
import com.ubat.elibraryai.data.Category
import com.ubat.elibraryai.data.Stats
import com.ubat.elibraryai.data.ChatMessageRequest
import com.ubat.elibraryai.data.ChatRequest
import com.ubat.elibraryai.data.LibraryBook
import com.ubat.elibraryai.data.Session
import com.ubat.elibraryai.data.errorMessage
import kotlinx.coroutines.launch

/** Root: signed-out flow (welcome/login/register) or signed-in app with bottom navigation. */
@Composable
fun AppRoot(vm: AppViewModel) {
    if (vm.user == null) AuthFlow(vm) else MainScaffold(vm)
}

// ------------------------------------------------------------------ signed-out
@Composable
fun AuthFlow(vm: AppViewModel) {
    var screen by rememberSaveable { mutableStateOf("welcome") }
    when (screen) {
        "welcome" -> WelcomeScreen(
            vm,
            onLogin = { vm.clearError(); screen = "login" },
            onRegister = { vm.clearError(); screen = "register" },
        )
        "login" -> AuthForm(vm, isRegister = false, onSwitch = { vm.clearError(); screen = "register" }, onBack = { vm.clearError(); screen = "welcome" })
        else -> AuthForm(vm, isRegister = true, onSwitch = { vm.clearError(); screen = "login" }, onBack = { vm.clearError(); screen = "welcome" })
    }
}

@Composable
fun WelcomeScreen(vm: AppViewModel, onLogin: () -> Unit, onRegister: () -> Unit) {
    Box(Modifier.fillMaxSize().background(Maroon)) {
        Column(
            Modifier.fillMaxWidth().padding(horizontal = 24.dp).align(Alignment.Center),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text("BRAIN STACK", color = Color.White, fontSize = 26.sp, fontWeight = FontWeight.ExtraBold)
            Spacer(Modifier.height(6.dp))
            Text(
                "Discover. Learn. Read. Smarter.",
                color = Color.White.copy(alpha = 0.9f),
                fontSize = 12.sp,
                textAlign = TextAlign.Center,
            )
            Spacer(Modifier.height(30.dp))
            Button(
                onClick = vm::continueAsGuest,
                enabled = !vm.loading,
                modifier = Modifier.fillMaxWidth().height(42.dp),
                shape = CircleShape,
                colors = androidx.compose.material3.ButtonDefaults.buttonColors(
                    containerColor = Color.White,
                    contentColor = Maroon,
                ),
            ) {
                Text(if (vm.loading) "Please wait..." else "Continue as Guest", fontSize = 12.sp)
            }
            Spacer(Modifier.height(14.dp))
            OutlinedButton(
                onClick = onLogin,
                modifier = Modifier.fillMaxWidth().height(42.dp),
                shape = CircleShape,
                border = BorderStroke(1.dp, Color.White),
                colors = androidx.compose.material3.ButtonDefaults.outlinedButtonColors(contentColor = Color.White),
            ) {
                Text("Sign in", fontSize = 12.sp)
            }
            Spacer(Modifier.height(8.dp))
            TextButton(onClick = onRegister) {
                Text("Create an account", color = Color.White, fontSize = 12.sp)
            }
            vm.error?.let {
                Spacer(Modifier.height(12.dp))
                Text(it, color = Color(0xFFFFD6DA), textAlign = TextAlign.Center)
            }
        }
    }
}

@Composable
fun AuthForm(vm: AppViewModel, isRegister: Boolean, onSwitch: () -> Unit, onBack: () -> Unit) {
    var name by rememberSaveable { mutableStateOf("") }
    var email by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.Center,
    ) {
        TextButton(onClick = onBack) { Text("< Back") }
        Text(if (isRegister) "Create your account" else "Welcome back", fontSize = 26.sp, fontWeight = FontWeight.Bold, color = Maroon)
        Spacer(Modifier.height(16.dp))
        if (isRegister) {
            OutlinedTextField(name, { name = it }, label = { Text("Full name") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(8.dp))
        }
        OutlinedTextField(
            email, { email = it }, label = { Text("Email") }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email), modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(
            password, { password = it }, label = { Text("Password") }, singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            supportingText = if (isRegister) ({ Text("At least 8 characters, letters and numbers") }) else null,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password), modifier = Modifier.fillMaxWidth(),
        )
        vm.error?.let { Spacer(Modifier.height(8.dp)); Text(it, color = MaterialTheme.colorScheme.error) }
        vm.notice?.let { Spacer(Modifier.height(8.dp)); Text(it, color = Color(0xFF2E6B4F)) }
        Spacer(Modifier.height(16.dp))
        Button(
            onClick = { if (isRegister) vm.register(name, email, password) else vm.login(email, password) },
            enabled = !vm.loading && email.isNotBlank() && password.isNotEmpty() && (!isRegister || name.isNotBlank()),
            modifier = Modifier.fillMaxWidth(),
        ) {
            if (vm.loading) CircularProgressIndicator(Modifier.height(20.dp), color = Color.White, strokeWidth = 2.dp)
            else Text(if (isRegister) "Register" else "Sign in")
        }
        TextButton(onClick = onSwitch, modifier = Modifier.align(Alignment.CenterHorizontally)) {
            Text(if (isRegister) "Already registered? Sign in" else "No account? Register")
        }
        TextButton(
            onClick = { vm.resendVerification(email) },
            enabled = !vm.loading && email.isNotBlank(),
            modifier = Modifier.align(Alignment.CenterHorizontally),
        ) {
            Text("Resend verification email")
        }
    }
}

// ------------------------------------------------------------------ signed-in
private data class Tab(val label: String, val icon: androidx.compose.ui.graphics.vector.ImageVector)

@Composable
fun MainScaffold(vm: AppViewModel) {
    val tabs = listOf(
        Tab("Home", Icons.Default.Home), Tab("Books", Icons.Default.Search),
        Tab("AI Assistant", Icons.Default.Face), Tab("Profile", Icons.Default.Person),
    )
    var selected by rememberSaveable { mutableStateOf(0) }
    var openBookId by rememberSaveable { mutableStateOf<Int?>(null) }
    Scaffold(
        bottomBar = {
            NavigationBar {
                tabs.forEachIndexed { i, t ->
                    NavigationBarItem(selected == i, { selected = i; openBookId = null }, icon = { Icon(t.icon, t.label) }, label = { Text(t.label, fontSize = 11.sp) })
                }
            }
        },
    ) { padding ->
        Box(Modifier.padding(padding).fillMaxSize()) {
            val bookId = openBookId
            if (bookId != null) {
                BookDetailScreen(bookId, onBack = { openBookId = null })
            } else when (selected) {
                0 -> HomeTab(vm, onBrowse = { selected = 1 })
                1 -> BooksTab(onOpen = { openBookId = it })
                2 -> AiTab()
                else -> ProfileTab(vm)
            }
        }
    }
}

@Composable
fun HomeTab(vm: AppViewModel, onBrowse: () -> Unit) {
    val user = vm.user
    var me by remember { mutableStateOf<MeResponse?>(null) }
    var stats by remember { mutableStateOf<Stats?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) {
        try {
            stats = ApiClient.service.stats()
            me = ApiClient.service.me()
        } catch (e: Exception) { error = errorMessage(e) }
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp)) {
        Text(if (user?.role == "guest") "Welcome, Guest" else "Welcome, ${user?.full_name}", fontSize = 24.sp, fontWeight = FontWeight.Bold, color = Maroon)
        Spacer(Modifier.height(16.dp))
        me?.let { StatCard("${it.downloads_used} / ${it.download_limit}", "Downloads used (${it.downloads_remaining} remaining)") }
        stats?.let {
            StatCard("${it.books}", "Books in the library")
            StatCard("${it.registered_users}", "Registered users")
        }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        if (me == null && error == null) CircularProgressIndicator()
        Spacer(Modifier.height(12.dp))
        Button(onClick = onBrowse, modifier = Modifier.fillMaxWidth()) { Text("Browse books") }
        if (user?.role == "guest") {
            Spacer(Modifier.height(8.dp))
            Text("Guest Mode allows 5 downloads. Register (Profile > Log out > Create account) for 10.", color = Color.Gray, fontSize = 13.sp)
        }
    }
}

@Composable
private fun StatCard(value: String, label: String) {
    Card(Modifier.fillMaxWidth().padding(vertical = 4.dp), colors = CardDefaults.cardColors(containerColor = Color.White)) {
        Column(Modifier.padding(16.dp)) {
            Text(value, fontSize = 24.sp, fontWeight = FontWeight.Bold, color = Maroon)
            Text(label, color = Color.Gray)
        }
    }
}

@Composable
fun BooksTab(onOpen: (Int) -> Unit) {
    var query by rememberSaveable { mutableStateOf("") }
    var category by rememberSaveable { mutableStateOf("") }
    var categories by remember { mutableStateOf<List<Category>>(emptyList()) }
    var books by remember { mutableStateOf<List<Book>>(emptyList()) }
    var total by remember { mutableStateOf(0) }
    var page by remember { mutableStateOf(1) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(true) }
    val scope = rememberCoroutineScope()

    suspend fun fetch(p: Int) {
        loading = true
        error = null
        try {
            val res = ApiClient.service.books(q = query.ifBlank { null }, category = category.ifBlank { null }, page = p)
            books = if (p == 1) res.items else books + res.items
            total = res.total
            page = p
        } catch (e: Exception) {
            error = errorMessage(e)
        }
        loading = false
    }

    LaunchedEffect(Unit) {
        try { categories = ApiClient.service.categories() } catch (e: Exception) { error = errorMessage(e) }
    }
    LaunchedEffect(query, category) { fetch(1) }

    Column(Modifier.fillMaxSize().padding(horizontal = 16.dp)) {
        Spacer(Modifier.height(12.dp))
        OutlinedTextField(query, { query = it }, placeholder = { Text("Search books or authors...") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        LazyRow(Modifier.padding(vertical = 8.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            item { FilterChip(category.isEmpty(), { category = "" }, label = { Text("All") }) }
            items(categories) { c -> FilterChip(category == c.name, { category = c.name }, label = { Text("${c.name} (${c.count})") }) }
        }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Text("$total book(s) found", color = Color.Gray, fontSize = 13.sp)
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
            items(books, key = { it.id }) { b ->
                Card(
                    onClick = { onOpen(b.id) },
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = Color.White),
                ) {
                    Column(Modifier.padding(14.dp)) {
                        Text(b.title, fontWeight = FontWeight.Bold)
                        Text(b.author, color = Color.Gray, fontSize = 13.sp)
                        Text("${b.category} · ${b.license}", color = Maroon, fontSize = 12.sp)
                    }
                }
            }
            item {
                if (loading) {
                    Box(Modifier.fillMaxWidth().padding(16.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                } else if (books.size < total) {
                    OutlinedButton(onClick = { scope.launch { fetch(page + 1) } }, modifier = Modifier.fillMaxWidth()) { Text("Load more") }
                }
            }
        }
    }
}

@Composable
fun BookDetailScreen(id: Int, onBack: () -> Unit) {
    var book by remember { mutableStateOf<BookDetail?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var info by remember { mutableStateOf<String?>(null) }
    var link by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val uriHandler = LocalUriHandler.current

    BackHandler(onBack = onBack)
    LaunchedEffect(id) {
        try { book = ApiClient.service.bookDetail(id) } catch (e: Exception) { error = errorMessage(e) }
    }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp)) {
        TextButton(onClick = onBack) { Text("< Back") }
        val b = book
        if (b == null && error == null) CircularProgressIndicator()
        if (b != null) {
            Text(b.category, color = Maroon, fontSize = 13.sp)
            Text(b.title, fontSize = 24.sp, fontWeight = FontWeight.Bold)
            Text("by ${b.author}", color = Color.Gray)
            Spacer(Modifier.height(12.dp))
            Text(b.description.ifBlank { "No description available." })
            Spacer(Modifier.height(8.dp))
            Text("License: ${b.license}", fontWeight = FontWeight.SemiBold)
            Text("Downloads used: ${b.downloads_used} of ${b.download_limit}" + if (b.already_downloaded) " (you already have this book)" else "", color = Color.Gray, fontSize = 13.sp)
            Spacer(Modifier.height(16.dp))
            Button(
                onClick = {
                    scope.launch {
                        busy = true
                        error = null
                        try {
                            val d = ApiClient.service.download(id)
                            info = "Ready! ${d.downloads_remaining} of ${d.download_limit} downloads remaining."
                            link = d.download_url
                            book = b.copy(already_downloaded = true, downloads_used = d.downloads_used)
                        } catch (e: Exception) {
                            error = errorMessage(e)
                        }
                        busy = false
                    }
                },
                enabled = !busy,
                modifier = Modifier.fillMaxWidth(),
            ) { Text(if (b.already_downloaded) "Get download link again" else "Download") }
        }
        info?.let { Spacer(Modifier.height(8.dp)); Text(it, color = Color(0xFF17622D)) }
        link?.let { url ->
            Spacer(Modifier.height(8.dp))
            OutlinedButton(onClick = { uriHandler.openUri(url) }, modifier = Modifier.fillMaxWidth()) { Text("Open book in browser") }
        }
        error?.let { Spacer(Modifier.height(8.dp)); Text(it, color = MaterialTheme.colorScheme.error) }
    }
}

/** Embedded Agentic AI assistant. */
@Composable
fun AiTab() {
    var input by rememberSaveable { mutableStateOf("") }
    var messages by remember { mutableStateOf<List<ChatMessageRequest>>(emptyList()) }
    var toolCalls by remember { mutableStateOf(0) }
    var books by remember { mutableStateOf<List<Book>>(emptyList()) }
    var error by remember { mutableStateOf<String?>(null) }
    var loading by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Session.token) {
        messages = emptyList()
        books = emptyList()
        toolCalls = 0
        try {
            val history = ApiClient.service.aiHistory()
            messages = history.messages
                .filter { it.role == "user" || it.role == "assistant" }
        } catch (e: Exception) {
            error = errorMessage(e)
        }
    }

    fun send(text: String) {
        if (text.isBlank() || loading) return
        val updated = messages + ChatMessageRequest("user", text)
        messages = updated
        input = ""
        scope.launch {
            loading = true
            error = null
            try {
                val response = ApiClient.service.aiChat(ChatRequest(updated.takeLast(12)))
                messages = messages + ChatMessageRequest("assistant", response.reply)
                toolCalls = response.tool_calls_made.size
                books = response.books
            } catch (e: Exception) {
                error = errorMessage(e)
            }
            loading = false
        }
    }

    Column(Modifier.fillMaxSize().padding(16.dp)) {
        Text("AI Assistant", fontSize = 24.sp, fontWeight = FontWeight.Bold, color = Maroon)
        Text("Search, compare, and recommend from the live library.", color = Color.Gray, fontSize = 13.sp)
        Spacer(Modifier.height(10.dp))

        LazyColumn(
            modifier = Modifier.weight(1f).fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (messages.isEmpty()) {
                item {
                    Card(colors = CardDefaults.cardColors(containerColor = Color.White)) {
                        Column(Modifier.padding(14.dp)) {
                            Text("Try asking:", fontWeight = FontWeight.Bold)
                            Text("• recommend mystery books")
                            Text("• search for Sherlock Holmes")
                            Text("• details of book 17")
                            Text("• compare 12 and 45")
                        }
                    }
                }
            }
            items(messages.size) { index ->
                val message = messages[index]
                val isUser = message.role == "user"
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(
                        containerColor = if (isUser) Maroon else Color(0xFFF2F2F2),
                    ),
                ) {
                    Text(
                        message.content,
                        modifier = Modifier.padding(12.dp),
                        color = if (isUser) Color.White else Color.Black,
                    )
                }
            }
            if (loading) item { CircularProgressIndicator(Modifier.padding(8.dp)) }
            if (toolCalls > 0) item {
                Text(
                    "$toolCalls real database tool call(s) made",
                    color = Maroon,
                    fontWeight = FontWeight.SemiBold,
                    fontSize = 13.sp,
                )
            }
            items(books, key = { it.id }) { book ->
                Card(colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF7F8))) {
                    Column(Modifier.padding(12.dp)) {
                        Text(book.title, fontWeight = FontWeight.Bold)
                        Text("${book.author} · ${book.category}", color = Color.Gray, fontSize = 12.sp)
                    }
                }
            }
        }

        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                input,
                { input = it },
                modifier = Modifier.weight(1f),
                placeholder = { Text("Ask about books...") },
                singleLine = true,
            )
            Spacer(Modifier.padding(4.dp))
            Button(onClick = { send(input) }, enabled = !loading && input.isNotBlank()) {
                Text("Send")
            }
        }
    }
}

@Composable
fun ProfileTab(vm: AppViewModel) {
    val user = vm.user
    var library by remember { mutableStateOf<List<LibraryBook>>(emptyList()) }
    var libraryError by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(user?.role) {
        if (user?.role != "guest") {
            try { library = ApiClient.service.library() }
            catch (e: Exception) { libraryError = errorMessage(e) }
        }
    }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp)) {
        Text("Profile", fontSize = 24.sp, fontWeight = FontWeight.Bold, color = Maroon)
        Spacer(Modifier.height(16.dp))
        Text(user?.full_name ?: "", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
        Text(user?.email ?: "Guest session (no account)", color = Color.Gray)
        Text("Role: ${user?.role}", color = Color.Gray)
        Spacer(Modifier.height(24.dp))
        Button(onClick = vm::logout, modifier = Modifier.fillMaxWidth()) { Text("Log out") }
        Spacer(Modifier.height(24.dp))
        Text("My Library", fontSize = 20.sp, fontWeight = FontWeight.Bold, color = Maroon)
        Spacer(Modifier.height(8.dp))
        if (user?.role == "guest") {
            Text("Guest accounts cannot use My Library. Create a registered account.", color = Color.Gray)
        } else if (libraryError != null) {
            Text(libraryError ?: "", color = MaterialTheme.colorScheme.error)
        } else if (library.isEmpty()) {
            Text("No favorites saved yet.", color = Color.Gray)
        } else {
            library.forEach { book ->
                Card(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                    Column(Modifier.padding(12.dp)) {
                        Text(book.title, fontWeight = FontWeight.Bold)
                        Text("${book.author} · ${book.category}", color = Color.Gray, fontSize = 12.sp)
                        TextButton(onClick = {
                            scope.launch {
                                try {
                                    ApiClient.service.removeFromLibrary(book.id)
                                    library = library.filterNot { it.id == book.id }
                                } catch (e: Exception) { libraryError = errorMessage(e) }
                            }
                        }) { Text("Remove") }
                    }
                }
            }
        }
    }
}
