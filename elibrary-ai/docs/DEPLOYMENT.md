# Deploying to Wasmer (backend + website)

Wasmer's documentation describes Python apps deployed with `wasmer deploy` using an `app.yaml` (and `wasmer.toml`),
persistent volumes, and a managed MySQL/PostgreSQL database. Wasmer's setup changes over time, so
follow the current guide at https://docs.wasmer.io/edge/quickstart/python and adapt it:

1. `wasmer login`
2. Create a Python app from Wasmer's template (`wasmer app create`) and compare its `app.yaml` / `wasmer.toml` / start command with this project.
3. Start command should run `python backend/run.py` (it reads `HOST` and `PORT` from the environment).
4. Add dependencies from `backend/requirements.txt` as the template requires.
5. Set env vars `JWT_SECRET` (long random string) and `DATABASE_PATH`.
6. **Persistence:** SQLite data is lost on redeploy unless the file lives on a mounted volume. In `app.yaml` add
   ```yaml
   volumes:
     - name: data
       mount: /data
   ```
   and set `DATABASE_PATH=/data/elibrary.db`. (Alternative: Wasmer's managed PostgreSQL - needs code changes, planned for Phase 2/3.)
7. `wasmer deploy` - note the app URL. Test `https://<app-url>/api/health`.
8. Put that URL in `android/gradle.properties` as `BASE_URL=https://<app-url>/` and rebuild the APK.
9. For https, remove `android:usesCleartextTraffic="true"` from `AndroidManifest.xml`.
If you get stuck, you can present Phase 1 from localhost + emulator and deploy by Phase 2.
