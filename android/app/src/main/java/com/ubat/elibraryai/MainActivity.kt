package com.ubat.elibraryai

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.lifecycle.viewmodel.compose.viewModel
import com.ubat.elibraryai.data.Session
import com.ubat.elibraryai.ui.AppRoot
import com.ubat.elibraryai.ui.ELibraryTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Session.init(applicationContext)
        setContent {
            ELibraryTheme {
                AppRoot(viewModel<AppViewModel>())
            }
        }
    }
}
