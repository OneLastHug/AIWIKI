# 文件：apps/android/app/src/main/java/ai/openclaw/app/ui/ProvidersModelsScreen.kt

## 文件职责初判
请把这个页面当作源码旁白。当前基础版先展示源码节选和阅读提示；后续深度讲解任务会补充函数级解释、调用关系和小白类比。

## 阅读提示
- 先看“引入的依赖”：文件开头的 `import` / `require` 会告诉你这个文件站在哪一层。
- 再看“对外提供的内容”：`export` / `class` / `function` 分别表示导出、类、函数。
- 最后看具体实现：理解输入、输出、副作用。

## 源码节选（保留原始代码，不翻译）
```text
package ai.openclaw.app.ui

import ai.openclaw.app.GatewayModelProviderSummary
import ai.openclaw.app.GatewayModelSummary
import ai.openclaw.app.MainViewModel
import ai.openclaw.app.providerDisplayName
import ai.openclaw.app.ui.design.ClawEmptyState
import ai.openclaw.app.ui.design.ClawPanel
import ai.openclaw.app.ui.design.ClawPrimaryButton
import ai.openclaw.app.ui.design.ClawScaffold
import ai.openclaw.app.ui.design.ClawSecondaryButton
import ai.openclaw.app.ui.design.ClawTheme
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

@Composable
internal fun ProvidersModelsScreen(
  viewModel: MainViewModel,
  onBack: () -> Unit,
  onAddProvider: () -> Unit,
) {
  val isConnected by viewModel.isConnected.collectAsState()
  val models by viewModel.modelCatalog.collectAsState()
  val providers by viewModel.modelAuthProviders.collectAsState()
  val refreshing by viewModel.modelCatalogRefreshing.collectAsState()
  val errorText by viewModel.modelCatalogErrorText.collectAsState()
  val providerRows = providerRows(providers = providers, models = models)
  val modelGroups = sortedModelGroups(models)
  val setupRows = providerSetupRows(providerRows)
  var expandedModelProviders by rememberSaveable { mutableStateOf(emptyList<String>()) }

  LaunchedEffect(isConnected) {
    if (isConnected) {
      viewModel.refreshModelCatalog()
    }
  }

  ClawScaffold(contentPadding = PaddingValues(start = 20.dp, top = 13.dp, end = 20.dp, bottom = 13.dp)) {
    Box(modifier = Modifier.fillMaxSize()) {
      LazyColumn(verticalArrangement = Arrangement.spacedBy(7.dp), contentPadding = PaddingValues(bottom = 112.dp)) {
        item {
          Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(
              modifier = Modifier.fillMaxWidth(),
              verticalAlignment = Alignment.CenterVertically,
              horizontalArrangement = Arrangement.SpaceBetween,
            ) {
              ProviderHeaderIconButton(icon = Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", onClick = onBack)
              ProviderHeaderIconButton(icon = Icons.Default.Add, contentDescription = "Add provider", outlined = true, onClick = onAddProvider)
            }
            Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
              Text(text = "Providers & Models", style = ClawTheme.type.display.copy(fontSize = 14.8.sp, lineHeight = 18.sp), color = ClawTheme.colors.text, maxLines = 1)
              Text(
                text = "Connect and manage AI providers\nBrowse models and their capabilities.",
                style = ClawTheme.type.caption.copy(fontSize = 12.5.sp, lineHeight = 16.sp),
                color = ClawTheme.colors.textMuted,
              )
            }
          }
        }

        item {
          ProviderOverviewPanel(
            isConnected = isConnected,
            providerRows = providerRows,
            modelCount = models.size,
            onRefresh = viewModel::refreshModelCatalog,
            onSetup = onAddProvider,
            refreshing = refreshing,
          )
        }

        item {
          ProviderSectionLabel(title = "Provider setup")
        }

        item {
          ProviderSetupList(rows = setupRows, onSetup = onAddProvider)
        }

        item {
          ProviderSectionLabel(title = "Connected providers")
        }

        item {
          if (!isConnected && providerRows.isEmpty()) {
            ClawEmptyState(title = "Gateway offline", body = "Connect your Gateway to load provider readiness and model catalog.")
          } else {
            ProviderList(rows = providerRows, refreshing = refreshing)
          }
        }

        errorText?.let { message ->
          item {
            ClawPanel {
              Text(text = message, style = ClawTheme.type.body, color = ClawTheme.colors.textMuted)
            }
          }
        }

        item {
          ProviderSectionLabel(title = "Model catalog")
        }

        if (modelGroups.isEmpty()) {
          item {
            ModelCatalogEmpty(
              title = if (refreshing) "Loading models" else "No models loaded",
              body = if (isConnected) "Refresh after configuring a provider on the Gateway." else "Connect the Gateway to browse models.",
            )
          }
        } else {
          items(modelGroups, key = { it.first }) { entry ->
            val expanded = expandedModelProviders.contains(entry.first)
            ModelGroup(
              provider = entry.first,
              models = entry.second,
              expanded = expanded,
              onToggle = {
                expandedModelProviders =
                  if (expanded) {
                    expandedModelProviders - entry.first
                  } else {
                    expandedModelProviders + entry.first
                  }
              },
            )
          }
        }
      }
      ProviderAddButton(onClick = onAddProvider, modifier = Modifier.align(Alignment.BottomCenter))
    }
  }
}

private data class ProviderSetupRow(
  val id: String,
  val name: String,
  val subtitle: String,
  val ready: Boolean,
)

private data class ProviderRow(
  val id: String,
  val name: String,
  val status: String,
  val ready: Boolean,
  val modelCount: Int,
)

private fun providerRows(
  providers: List<GatewayModelProviderSummary>,
  models: List<GatewayModelSummary>,
): List<ProviderRow> {
  val modelCounts = models.groupingBy { it.provider }.eachCount()
  val authRows =
    providers.map { provider ->
      val ready = modelProviderReady(provider.status)
      ProviderRow(
        id = provider.id,
        name = provider.displayName,
        status = if (ready) "Ready" else "Needs setup",
        ready = ready,
        modelCount = modelCounts[provider.id] ?: 0,
      )
    }
  val missingAuthRows =
    modelCounts.keys
      .filter { provider -> authRows.none { it.id == provider } }
      .map { provider ->
        ProviderRow(
          id = provider,
          name = providerDisplayName(provider),
          status = "Ready",
          ready = true,
          modelCount = modelCounts[provider] ?: 0,
        )
      }
  return (authRows + missingAuthRows).sortedWith(compareBy(::providerPriority, { it.name.lowercase() }))
}

private fun providerSetupRows(providerRows: List<ProviderRow>): List<ProviderSetupRow> {
  val byId = providerRows.associateBy { it.id.trim().lowercase() }
  return listOf("openai", "anthropic", "google", "openrouter", "ollama").map { id ->
    val row = byId[id] ?: byId["ollama-local"].takeIf { id == "ollama" }
    ProviderSetupRow(
      id = id,
      name = providerDisplayName(id),
      subtitle = providerSetupSubtitle(id, row),
      ready = row?.ready == true,
    )
  }
}

private fun providerSetupSubtitle(
  id: String,
  row: ProviderRow?,
): String =
  when {
    row?.ready == true -> if (row.modelCount > 0) "${row.modelCount} models available" else "Ready"
    row != null -> "Finish setup to use ${row.name}"
    id == "ollama" -> "Use models running on your network"
    else -> "Add provider credentials on your Gateway"
  }

internal fun modelProviderReady(status: String): Boolean {
  val normalized = status.trim().lowercase()
  return normalized == "ok" ||
    normalized == "ready" ||
    normalized == "healthy" ||
    normalized == "configured" ||
    normalized == "static"
}

private fun sortedModelGroups(models: List<GatewayModelSummary>): List<Pair<String, List<GatewayModelSummary>>> =
  models
    .groupBy { it.provider }
    .entries
    .sortedWith(compareBy({ providerPriority(it.key) }, { providerDisplayName(it.key).lowercase() }))
    .map { it.key to it.value }

private fun providerPriority(row: ProviderRow): Int = providerPriority(row.id)

private fun providerPriority(provider: String): Int =
  when (provider.trim().lowercase()) {
    "openai" -> 0
    "anthropic" -> 1
    "google" -> 2
    "openrouter" -> 3
    "ollama", "ollama-local" -> 4
    "codex", "openai-codex" -> 5
    else -> 100
  }

@Composable
private fun ProviderList(
  rows: List<ProviderRow>,
  refreshing: Boolean,
) {
  ClawPanel(contentPadding = PaddingValues(horizontal = 0.dp, vertical = 0.dp)) {
    Column {
      if (rows.isEmpty()) {
        ProviderListRow(ProviderRow(id = "loading", name = "Provider catalog", status = if (refreshing) "Loading" else "No providers", ready = false, modelCount = 0))
      } else {
        val visibleRows = rows.take(5)
        visibleRows.forEachIndexed { index, row ->
          ProviderListRow(row)
          if (index != visibleRows.lastIndex) {
            HorizontalDivider(color = ClawTheme.colors.border, thickness = 1.dp)
          }
        }
      }
    }
  }
}

@Composable
private fun ProviderOverviewPanel(
  isConnected: Boolean,
  providerRows: List<ProviderRow>,
  modelCount: Int,
  refreshing: Boolean,
  onRefresh: () -> Unit,
  onSetup: () -> Unit,
) {
  val readyCount = providerRows.count { it.ready }
  val needsSetupCount = providerRows.count { !it.ready }
  ClawPanel(contentPadding = PaddingValues(horizontal = 12.dp, vertical = 12.dp)) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
      Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        ProviderMetricTile(label = "Ready", value = readyCount.toString(), modifier = Modifier.weight(1f))
        ProviderMetricTile(label = "Models", value = modelCount.toString(), modifier = Modifier.weight(1f))
        ProviderMetricTile(label = "Setup", value = needsSetupCount.toString(), modifier = Modifier.weight(1f))
      }
      Text(
        text = if (isConnected) "Choose a provider below, then finish credentials on your Gateway." else "Connect your Gateway before adding model providers.",
        style = ClawTheme.type.body,
        color = ClawTheme.colors.textMuted,
      )
      Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        ClawSecondaryButton(text = if (refreshing) "Refreshing" else "Refresh", onClick = onRefresh, enabled = isConnected && !refreshing, modifier = Modifier.weight(1f))
        ClawPrimaryButton(text = "Setup Provider", onClick = onSetup, enabled = isConnected, modifier = Modifier.weight(1f))
      }
    }
  }
}

@Composable
private fun ProviderMetricTile(
  label: String,
  value: String,
  modifier: Modifier = Modifier,
) {
  Surface(
    modifier = modifier,
    shape = RoundedCornerShape(ClawTheme.radii.panel),
    color = ClawTheme.colors.surface,
    border = BorderStroke(1.dp, ClawTheme.colors.border),
    contentColor = ClawTheme.colors.text,
  ) {
    Column(modifier = Modifier.padding(horizontal = 9.dp, vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
      Text(text = value, style = ClawTheme.type.title, color = ClawTheme.colors.text, maxLines = 1)
      Text(text = label, style = ClawTheme.type.caption, color = ClawTheme.colors.textMuted, maxLines = 1)
    }
  }
}

@Composable
private fun ProviderSetupList(
  rows: List<ProviderSetupRow>,
  onSetup: () -> Unit,
) {
  ClawPanel(contentPadding = PaddingValues(horizontal = 0.dp, vertical = 0.dp)) {
    Column {
      rows.forEachIndexed { index, row ->
        ProviderSetupListRow(row = row, onClick = onSetup)
        if (index != rows.lastIndex) {
          HorizontalDivider(color = ClawTheme.colors.border, thickness = 1.dp)
        }
      }
    }
  }
}

@Composable
private fun ProviderSetupListRow(
  row: ProviderSetupRow,
  onClick: () -> Unit,
) {
  Surface(onClick = onClick, color = Color.Transparent, contentColor = ClawTheme.colors.text) {
    Row(
      modifier = Modifier.fillMaxWidth().heightIn(min = 58.dp).padding(horizontal = 10.dp, vertical = 6.dp),
      verticalAlignment = Alignment.CenterVertically,
      horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
      ProviderBadge(text = row.name)
      Column(modifier = Modifier.we
...[truncated]
```
