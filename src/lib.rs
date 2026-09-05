mod diff;
mod error;
mod model;
mod patch;
mod paths;
mod pointer;
mod search;

pub use diff::diff;
pub use error::DriftError;
pub use model::{Delta, Operation};
pub use patch::patch;
pub use paths::list_json_paths;
pub use pointer::{escape_token, join_pointer, split_pointer, unescape_token};
pub use search::{filter_operations, path_matches};

pub const VERSION: &str = "0.12.0";

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn nested_diff_round_trips() {
        let old = json!({"a": {"b": [1, 2]}});
        let new = json!({"a": {"b": [1, 3, 4]}});
        assert_eq!(patch(old.clone(), &diff(&new, &old)).unwrap(), new);
    }

    #[test]
    fn pointers_escape() {
        assert_eq!(join_pointer("", "a/b~c"), "/a~1b~0c");
        assert_eq!(split_pointer("/a~1b~0c").unwrap(), vec!["a/b~c"]);
    }

    #[test]
    fn arrays_insert() {
        let old = json!([1, 2]);
        let operation = Delta::with_value(Operation::Add, "/1", json!(9));
        assert_eq!(patch(old, &[operation]).unwrap(), json!([1, 9, 2]));
    }
}
