<?php
// 設定資料檔案路徑
$my_script_name = basename(__FILE__);

// 1. YAML 階層解析器 (建構字典與階層樹)
function load_tag_hierarchy($filepath) {
    assert(file_exists($filepath), "Taxonomy file not found: $filepath");
    $lines = file($filepath, FILE_IGNORE_NEW_LINES);
    
    $parsed_nodes = [];
    foreach ($lines as $line) {
        if (trim($line) === '' || preg_match('/^\s*#/', $line)) continue;
        
        preg_match('/^(\s*)([^#:]+):/', $line, $matches);
        if ($matches) {
            $indent = strlen($matches[1]);
            $tag = trim($matches[2]);
            $parsed_nodes[] = ['indent' => $indent, 'tag' => $tag];
        }
    }

    $parent_stack = [];
    $children_map = [];
    $root_tags = [];
    $all_tags = [];

    foreach ($parsed_nodes as $node) {
        $indent = $node['indent'];
        $tag = $node['tag'];
        $all_tags[$tag] = true;

        while (!empty($parent_stack) && end($parent_stack)['indent'] >= $indent) {
            array_pop($parent_stack);
        }

        if (!empty($parent_stack)) {
            $parent_tag = end($parent_stack)['tag'];
            $children_map[$parent_tag][] = $tag;
        } else {
            $root_tags[] = $tag;
        }

        $parent_stack[] = ['indent' => $indent, 'tag' => $tag];
    }

    // 取得各標籤包含自身與所有子孫的集合
    $descendants_map = [];
    $get_descendants = function($t) use (&$get_descendants, &$children_map) {
        $res = [$t];
        if (isset($children_map[$t])) {
            foreach ($children_map[$t] as $child) {
                $res = array_merge($res, $get_descendants($child));
            }
        }
        return array_unique($res);
    };

    foreach (array_keys($all_tags) as $t) {
        $descendants_map[$t] = $get_descendants($t);
    }

    return [
        'root_tags' => $root_tags,
        'children_map' => $children_map,
        'descendants_map' => $descendants_map,
        'all_tags' => $all_tags
    ];
}

$taxonomy = load_tag_hierarchy('tag-hierarchy.yaml');
$descendants_map = $taxonomy['descendants_map'];

// 2. 解析查詢參數
if (PHP_SAPI === 'cli') {
    parse_str(implode('&', array_slice($argv, 1)), $_GET);
}

$query_expression = isset($_GET['T']) ? trim($_GET['T']) : '';

$product_groups_expanded = [];
$query_terms = []; 

if ($query_expression !== '') {
    $products = preg_split('/[\s+]/', $query_expression);
    foreach ($products as $prod) {
        $raw_terms = preg_split('/[*]/', $prod);
        $raw_terms = array_filter(array_map('trim', $raw_terms));
        
        if (!empty($raw_terms)) {
            $term_group_expanded = [];
            foreach ($raw_terms as $term) {
                $query_terms[] = $term;
                
                // 處理驚嘆號: 若有 '!' 則僅搜尋該標籤本身，不展開子孫
                if (substr($term, -1) === '!') {
                    $clean_term = substr($term, 0, -1);
                    $term_group_expanded[] = [$clean_term];
                } else {
                    if (isset($descendants_map[$term])) {
                        $term_group_expanded[] = $descendants_map[$term];
                    } else {
                        $term_group_expanded[] = [$term];
                    }
                }
            }
            $product_groups_expanded[] = $term_group_expanded;
        }
    }
    $query_terms = array_unique($query_terms);
}

$db = new PDO('sqlite:plurk_tags.db');
$db->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

/**
 * 共用核心邏輯：將單一 Product Group（AND 條件組合）轉為 SQL 與 Bind Parameters
 */
function build_product_group_sql($term_group, &$bind_params) {
    $term_count = count($term_group);
    $case_exprs = [];
    $all_flattened_tags = [];
    
    foreach ($term_group as $tag_set) {
        $placeholders = implode(',', array_fill(0, count($tag_set), '?'));
        $case_exprs[] = "MAX(CASE WHEN t.tag IN ($placeholders) THEN 1 ELSE 0 END)";
        $all_flattened_tags = array_merge($all_flattened_tags, $tag_set);
    }

    $having_clause = "(" . implode(" + ", $case_exprs) . ") = $term_count";
    $all_placeholders = implode(',', array_fill(0, count($all_flattened_tags), '?'));

    $sql = "
        SELECT p.id, p.ts, p.content
        FROM plurk p
        LEFT JOIN plurk_tag t ON p.id = t.plurk_id
        WHERE t.tag IN ($all_placeholders)
        GROUP BY p.id
        HAVING $having_clause
    ";

    $bind_params = array_merge($bind_params, $all_flattened_tags);
    foreach ($term_group as $tag_set) {
        $bind_params = array_merge($bind_params, $tag_set);
    }

    return $sql;
}
?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">

<html xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
  <meta name="generator" content="HTML Tidy for Linux/x86 (vers 25 March 2009), see www.w3.org" />
  <?php include "../../iu/meta.php"; ?>
  <link rel="stylesheet" type="text/css" href="plurk.css" />

  <?php $query_expression = preg_replace('/\s+/', ' + ', $query_expression); ?>
  <title>[ <?php echo $query_expression; ?> ] -- 貴哥的噗 by tags</title>
  <style type="text/css">
/*<![CDATA[*/
  span.c1 {text-decoration: line-through}
  /*]]>*/
  </style>
</head>

<body>
  <?php include "../../iu/header.php"; ?>

  <div id="content">

  <h1>[ <?php echo $query_expression; ?> ] -- 貴哥的噗 by tags</h1>

<?php
if (empty($query_terms)) {
    // 1. 取得資料庫中實際存在的所有標籤
    $stmt = $db->query("SELECT DISTINCT tag FROM plurk_tag");
    $db_tags = $stmt->fetchAll(PDO::FETCH_COLUMN);

    // 建立臨時映射表 (In-Memory Temporary Table) 用於計算包含子孫的噗筆數
    $db->exec("CREATE TEMP TABLE IF NOT EXISTS tag_expansion (parent_tag TEXT, child_tag TEXT)");
    $db->exec("DELETE FROM tag_expansion");

    $insert_stmt = $db->prepare("INSERT INTO tag_expansion (parent_tag, child_tag) VALUES (?, ?)");

    $known_parents = [];
    foreach ($db_tags as $tag) {
        $known_parents[$tag] = true;
        $descendants = isset($descendants_map[$tag]) ? $descendants_map[$tag] : [$tag];
        foreach ($descendants as $desc) {
            $insert_stmt->execute([$tag, $desc]);
        }
    }

    foreach ($descendants_map as $parent => $descendants) {
        if (!isset($known_parents[$parent])) {
            foreach ($descendants as $desc) {
                $insert_stmt->execute([$parent, $desc]);
            }
        }
    }

    // 統計每個 tag（包含其子孫標籤）的 DISTINCT plurk_id 數
    $sql_count = "
        SELECT e.parent_tag AS tag, COUNT(DISTINCT t.plurk_id) AS times
        FROM tag_expansion e
        JOIN plurk_tag t ON e.child_tag = t.tag
        GROUP BY e.parent_tag
    ";

    $stmt_count = $db->query($sql_count);
    $counts = [];
    while ($row = $stmt_count->fetch(PDO::FETCH_ASSOC)) {
        $counts[$row['tag']] = (int)$row['times'];
    }

    // 收集資料庫中有出現但未於 YAML 階層定義的孤兒標籤
    $orphan_tags = [];
    foreach ($db_tags as $t) {
        if (!isset($taxonomy['all_tags'][$t])) {
            $orphan_tags[] = $t;
        }
    }

    // 2. 遞迴印出 HTML 樹形結構 (同層按 times 降序排列，嚴格按層級 4 空格縮排)
    $render_tree = function($tag_list, $depth = 0) use (&$render_tree, $taxonomy, $counts, $my_script_name) {
        if (empty($tag_list)) return;

        // 同層級按噗數 (times) 降序排列，若相同則按字元排序
        usort($tag_list, function($a, $b) use ($counts) {
            $cnt_a = isset($counts[$a]) ? $counts[$a] : 0;
            $cnt_b = isset($counts[$b]) ? $counts[$b] : 0;
            if ($cnt_a !== $cnt_b) {
                return $cnt_b <=> $cnt_a;
            }
            return strcmp($a, $b);
        });

        $indent_ul = str_repeat(" ", $depth * 4);
        $indent_li = str_repeat(" ", ($depth + 1) * 4);

        echo "{$indent_ul}<ul>\n";
        foreach ($tag_list as $tag) {
            $times = isset($counts[$tag]) ? $counts[$tag] : 0;
            if ($times === 0) continue; // 不呈現總筆數為 0 的標籤

            $encoded_tag = urlencode($tag);
            $safe_tag = htmlspecialchars($tag, ENT_NOQUOTES, 'UTF-8');

            if (isset($taxonomy['children_map'][$tag]) && !empty($taxonomy['children_map'][$tag])) {
                echo "{$indent_li}<li>{$times} <a href='{$my_script_name}?T={$encoded_tag}'>{$safe_tag}</a>\n";
                $render_tree($taxonomy['children_map'][$tag], $depth + 2);
                echo "{$indent_li}</li>\n";
            } else {
                echo "{$indent_li}<li>{$times} <a href='{$my_script_name}?T={$encoded_tag}'>{$safe_tag}</a></li>\n";
            }
        }
        echo "{$indent_ul}</ul>\n";
    };

    // 渲染定義於 YAML 內的階層樹
    $render_tree($taxonomy['root_tags'], 0);

    // 若有孤兒標籤，獨立呈現於底端
    if (!empty($orphan_tags)) {
        $render_tree($orphan_tags, 0);
    }

    echo "</div>\n";
    include "$top[fs]/iu/navigator.php";
    echo "</body>\n</html>\n";
    exit;
}

// 3. 處理有查詢條件 (Sum of Products) 的狀況
$union_queries = [];
$bind_params = [];

foreach ($product_groups_expanded as $term_group) {
    $union_queries[] = build_product_group_sql($term_group, $bind_params);
}

$sql = "SELECT * FROM (" . implode(" UNION ", $union_queries) . ") ORDER BY ts DESC";

$stmt = $db->prepare($sql);
$stmt->execute($bind_params);

$matched_plurks = $stmt->fetchAll(PDO::FETCH_ASSOC);

echo "<ul>\n";
foreach ($matched_plurks as $plurk) {
    $id = $plurk['id'];
    $ts = $plurk['ts'];
    $content = $plurk['content'];
    
    if (isset($_GET['id']) && trim($_GET['T'])) {
        $content = preg_replace('/^(<li>)?/', '$1' . "$id ", $content);
    }
        
    $stmt_tags = $db->prepare("SELECT tag FROM plurk_tag WHERE plurk_id = ?");
    $stmt_tags->execute([$id]);
    $tags = $stmt_tags->fetchAll(PDO::FETCH_COLUMN);
    
    $tag_links = [];
    foreach ($tags as $tag) {
        $encoded_tag = urlencode($tag);
        $safe_tag = htmlspecialchars($tag, ENT_NOQUOTES, 'UTF-8');
        $tag_links[] = "<a href=\"{$my_script_name}?T={$encoded_tag}\" class=\"tag\">{$safe_tag}</a>";
    }
    $tags_output = empty($tag_links) ? ' ' : "<br />標籤： " . implode(' ', $tag_links);
    
    echo "    <li>$content . $tags_output</li>\n";
}
echo "</ul>\n";
?>

  </div><?php include "$top[fs]/iu/navigator.php"; ?>
</body>
</html>
