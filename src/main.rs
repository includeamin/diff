mod cli;
mod formats;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    cli::run()
}
